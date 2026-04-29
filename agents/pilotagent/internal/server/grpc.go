package server

import (
	"time"

	pilotmetricspb "github.com/univ-lehavre/cluster-pilot/agents/pilotagent/gen/pilotmetrics/v1alpha1"
	"github.com/univ-lehavre/cluster-pilot/agents/pilotagent/internal/metrics"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type MetricsServer struct {
	pilotmetricspb.UnimplementedMetricsServer
	ProcStatPath string
}

func (s *MetricsServer) StreamCpu(req *pilotmetricspb.CpuRequest, stream pilotmetricspb.Metrics_StreamCpuServer) error {
	interval := time.Duration(req.IntervalSeconds * float64(time.Second))
	if interval <= 0 {
		interval = time.Second
	}

	sampler := metrics.NewCPUSampler(interval)
	if s.ProcStatPath != "" {
		sampler.ProcStatPath = s.ProcStatPath
	}

	ctx := stream.Context()
	for {
		sample, err := sampler.Sample(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return status.Errorf(codes.Internal, "sample CPU: %v", err)
		}

		if err := stream.Send(&pilotmetricspb.CpuSample{
			UsagePercent: sample.UsagePercent,
			TimestampMs:  sample.Timestamp.UnixMilli(),
		}); err != nil {
			return err
		}
	}
}
