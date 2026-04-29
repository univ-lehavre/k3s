package metrics

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

const DefaultProcStatPath = "/proc/stat"

type CPUStat struct {
	Idle  uint64
	Total uint64
}

type CPUSample struct {
	UsagePercent float64   `json:"usagePercent"`
	Timestamp    time.Time `json:"timestamp"`
}

type CPUSampler struct {
	ProcStatPath string
	Interval     time.Duration
}

func NewCPUSampler(interval time.Duration) CPUSampler {
	return CPUSampler{
		ProcStatPath: DefaultProcStatPath,
		Interval:     interval,
	}
}

func (sampler CPUSampler) Sample(ctx context.Context) (CPUSample, error) {
	interval := sampler.Interval
	if interval <= 0 {
		interval = time.Second
	}

	prev, err := ReadCPUStat(sampler.ProcStatPath)
	if err != nil {
		return CPUSample{}, err
	}

	timer := time.NewTimer(interval)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return CPUSample{}, ctx.Err()
	case <-timer.C:
	}

	cur, err := ReadCPUStat(sampler.ProcStatPath)
	if err != nil {
		return CPUSample{}, err
	}

	usage, ok := UsagePercent(prev, cur)
	if !ok {
		return CPUSample{}, errors.New("cannot compute CPU usage from non-increasing counters")
	}

	return CPUSample{
		UsagePercent: usage,
		Timestamp:    time.Now().UTC(),
	}, nil
}

func ReadCPUStat(path string) (CPUStat, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return CPUStat{}, err
	}

	lines := strings.Split(string(content), "\n")
	if len(lines) == 0 {
		return CPUStat{}, errors.New("empty proc stat")
	}

	return ParseCPUStatLine(lines[0])
}

func ParseCPUStatLine(line string) (CPUStat, error) {
	fields := strings.Fields(line)
	if len(fields) < 5 {
		return CPUStat{}, fmt.Errorf("invalid CPU stat line: %q", line)
	}
	if fields[0] != "cpu" {
		return CPUStat{}, fmt.Errorf("expected aggregate cpu line, got %q", fields[0])
	}

	values := make([]uint64, 0, len(fields)-1)
	var total uint64
	for _, field := range fields[1:] {
		value, err := strconv.ParseUint(field, 10, 64)
		if err != nil {
			return CPUStat{}, fmt.Errorf("invalid CPU counter %q: %w", field, err)
		}
		values = append(values, value)
		total += value
	}

	idle := values[3]
	if len(values) > 4 {
		idle += values[4]
	}

	return CPUStat{Idle: idle, Total: total}, nil
}

func UsagePercent(prev CPUStat, cur CPUStat) (float64, bool) {
	if cur.Total <= prev.Total || cur.Idle < prev.Idle {
		return 0, false
	}

	totalDelta := cur.Total - prev.Total
	idleDelta := cur.Idle - prev.Idle
	if idleDelta > totalDelta {
		return 0, false
	}

	return float64(totalDelta-idleDelta) * 100 / float64(totalDelta), true
}
