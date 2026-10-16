// Package main implements the Go gRPC gateway in front of the Ray Serve
// deployment. It translates gRPC requests into Ray Serve HTTP calls.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	pb "github.com/RealTimeMilo/data_engineering_project/containers/inference_rpc/gen"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"
)

type rayResponse struct {
	Probabilities []float64 `json:"probabilities"`
	Model         string    `json:"model"`
}

type server struct {
	pb.UnimplementedInferenceServer
	rayURL string
	client *http.Client
}

func (s *server) rayPost(ctx context.Context, path string, payload any) (*rayResponse, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal: %v", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.rayURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, status.Errorf(codes.Internal, "request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, status.Errorf(codes.Unavailable, "ray serve unreachable: %v", err)
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, status.Errorf(codes.FailedPrecondition, "ray serve %d: %s", resp.StatusCode, string(raw))
	}
	var out rayResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, status.Errorf(codes.Internal, "decode: %v", err)
	}
	return &out, nil
}

func (s *server) Health(ctx context.Context, _ *pb.HealthRequest) (*pb.HealthResponse, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.rayURL+"/health", nil)
	if err != nil {
		return &pb.HealthResponse{Status: "error", Detail: err.Error()}, nil
	}
	resp, err := s.client.Do(req)
	if err != nil {
		return &pb.HealthResponse{Status: "error", RayReady: false, Detail: err.Error()}, nil
	}
	defer resp.Body.Close()
	return &pb.HealthResponse{Status: "ok", RayReady: resp.StatusCode == http.StatusOK}, nil
}

func (s *server) Predict(ctx context.Context, in *pb.PredictRequest) (*pb.PredictResponse, error) {
	instances := make([]map[string]float64, 0, len(in.GetInstances()))
	for _, inst := range in.GetInstances() {
		row := make(map[string]float64, len(inst.GetFeatures()))
		for _, f := range inst.GetFeatures() {
			row[f.GetName()] = f.GetValue()
		}
		instances = append(instances, row)
	}
	res, err := s.rayPost(ctx, "/predict", map[string]any{"instances": instances})
	if err != nil {
		return nil, err
	}
	return &pb.PredictResponse{Probabilities: res.Probabilities, Model: res.Model}, nil
}

func (s *server) PredictOnline(ctx context.Context, in *pb.OnlineRequest) (*pb.PredictResponse, error) {
	entities := make([]map[string]int64, 0, len(in.GetEntities()))
	for _, e := range in.GetEntities() {
		entities = append(entities, map[string]int64{"user_id": e.GetUserId(), "product_id": e.GetProductId()})
	}
	res, err := s.rayPost(ctx, "/predict_online", map[string]any{"entities": entities})
	if err != nil {
		return nil, err
	}
	return &pb.PredictResponse{Probabilities: res.Probabilities, Model: res.Model}, nil
}

func main() {
	port := os.Getenv("GRPC_PORT")
	if port == "" {
		port = "50051"
	}
	rayURL := os.Getenv("RAY_SERVE_URL")
	if rayURL == "" {
		rayURL = "http://localhost:8000"
	}

	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("listen: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterInferenceServer(grpcServer, &server{
		rayURL: rayURL,
		client: &http.Client{Timeout: 30 * time.Second},
	})

	// Standard gRPC health service (for the NLB/health checks) + reflection.
	hs := health.NewServer()
	hs.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
	healthpb.RegisterHealthServer(grpcServer, hs)
	reflection.Register(grpcServer)

	fmt.Printf("inference gRPC gateway listening on :%s -> Ray Serve %s\n", port, rayURL)
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("serve: %v", err)
	}
}
