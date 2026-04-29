package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/univ-lehavre/cluster-pilot/agents/pilotagent/internal/metrics"
)

type cpuSample struct {
	UsagePercent float64 `json:"usagePercent"`
	TimestampMs  int64   `json:"timestampMs"`
}

func main() {
	interval := flag.Duration("interval", time.Second, "CPU sampling interval")
	samples := flag.Int("samples", 0, "number of samples to emit, 0 means forever")
	procStat := flag.String("proc-stat", metrics.DefaultProcStatPath, "path to proc stat")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	sampler := metrics.NewCPUSampler(*interval)
	sampler.ProcStatPath = *procStat

	encoder := json.NewEncoder(os.Stdout)
	for count := 0; *samples == 0 || count < *samples; count++ {
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
