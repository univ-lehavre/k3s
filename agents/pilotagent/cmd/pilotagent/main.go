package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	pilotmetricspb "github.com/univ-lehavre/cluster-pilot/agents/pilotagent/gen/pilotmetrics/v1alpha1"
	"github.com/univ-lehavre/cluster-pilot/agents/pilotagent/internal/metrics"
	"github.com/univ-lehavre/cluster-pilot/agents/pilotagent/internal/server"
	"google.golang.org/grpc"
)

type cpuSample struct {
	UsagePercent float64 `json:"usagePercent"`
	TimestampMs  int64   `json:"timestampMs"`
}

func main() {
	mode := flag.String("mode", "json", "output mode: json or grpc")
	addr := flag.String("addr", "127.0.0.1:50051", "gRPC listen address (mode=grpc)")
	interval := flag.Duration("interval", time.Second, "CPU sampling interval (mode=json)")
	samples := flag.Int("samples", 0, "number of samples to emit, 0 means forever (mode=json)")
	procStat := flag.String("proc-stat", metrics.DefaultProcStatPath, "path to proc stat")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	switch *mode {
	case "grpc":
		runGRPC(ctx, *addr, *procStat)
	default:
		runJSON(ctx, *interval, *samples, *procStat)
	}
}

func runGRPC(ctx context.Context, addr string, procStatPath string) {
	lis, err := net.Listen("tcp", addr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "listen %s: %v\n", addr, err)
		os.Exit(1)
	}

	srv := grpc.NewServer()
	pilotmetricspb.RegisterMetricsServer(srv, &server.MetricsServer{ProcStatPath: procStatPath})

	go func() {
		<-ctx.Done()
		srv.GracefulStop()
	}()

	fmt.Fprintf(os.Stderr, "pilotagent gRPC listening on %s\n", addr)
	if err := srv.Serve(lis); err != nil {
		fmt.Fprintf(os.Stderr, "serve: %v\n", err)
		os.Exit(1)
	}
}

func runJSON(ctx context.Context, interval time.Duration, maxSamples int, procStatPath string) {
	sampler := metrics.NewCPUSampler(interval)
	sampler.ProcStatPath = procStatPath

	encoder := json.NewEncoder(os.Stdout)
	for count := 0; maxSamples == 0 || count < maxSamples; count++ {
		sample, err := sampler.Sample(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			fmt.Fprintf(os.Stderr, "sample CPU: %v\n", err)
			os.Exit(1)
		}

		if err := encoder.Encode(cpuSample{
			UsagePercent: sample.UsagePercent,
			TimestampMs:  sample.Timestamp.UnixMilli(),
		}); err != nil {
			fmt.Fprintf(os.Stderr, "encode CPU sample: %v\n", err)
			os.Exit(1)
		}
	}
}
