// CLI client for the inference gRPC gateway.
//
//	RAY_RPC_ADDR=host:50051 go run ./client
package main

import (
	"context"
	"log"
	"os"
	"strconv"
	"time"

	pb "github.com/RealTimeMilo/data_engineering_project/containers/inference_rpc/gen"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	addr := os.Getenv("RAY_RPC_ADDR")
	if addr == "" {
		addr = "localhost:50051"
	}
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("dial: %v", err)
	}
	defer conn.Close()
	client := pb.NewInferenceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if h, err := client.Health(ctx, &pb.HealthRequest{}); err == nil {
		log.Printf("health: status=%s ray_ready=%v", h.GetStatus(), h.GetRayReady())
	}

	// Online (Feast) prediction. Entity ids can be overridden via env so the
	// CLI can target a pair that exists in the populated online store.
	userID := int64(1)
	productID := int64(196)
	if v := os.Getenv("RAY_RPC_USER_ID"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			userID = n
		}
	}
	if v := os.Getenv("RAY_RPC_PRODUCT_ID"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			productID = n
		}
	}
	res, err := client.PredictOnline(ctx, &pb.OnlineRequest{Entities: []*pb.Entity{
		{UserId: userID, ProductId: productID},
	}})
	if err != nil {
		log.Fatalf("PredictOnline: %v", err)
	}
	log.Printf("probabilities: %v  (model %s)", res.GetProbabilities(), res.GetModel())
}
