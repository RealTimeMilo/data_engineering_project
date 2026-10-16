# syntax=docker/dockerfile:1
# Build context is the repository root (see Makefile).

FROM golang:1.22-bookworm AS gen
RUN apt-get update \
    && apt-get install -y --no-install-recommends protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2 \
    && go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
ENV PATH="/root/go/bin:${PATH}"
WORKDIR /src
COPY containers/inference_rpc/proto ./proto
# protoc does not create the output directory, so make it first.
RUN mkdir -p gen && protoc -I proto \
    --go_out=gen --go_opt=paths=source_relative \
    --go-grpc_out=gen --go-grpc_opt=paths=source_relative \
    proto/inference.proto

FROM golang:1.22-bookworm AS build
WORKDIR /src
COPY containers/inference_rpc/go.mod ./
COPY --from=gen /src/gen ./gen
COPY containers/inference_rpc/main.go ./
COPY containers/inference_rpc/client ./client
RUN go mod tidy \
    && CGO_ENABLED=0 go build -o /out/inference-rpc . \
    && CGO_ENABLED=0 go build -o /out/inference-cli ./client

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/inference-rpc /inference-rpc
COPY --from=build /out/inference-cli /inference-cli
EXPOSE 50051
ENTRYPOINT ["/inference-rpc"]
