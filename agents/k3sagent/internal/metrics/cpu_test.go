package metrics

import (
	"math"
	"testing"
)

func TestParseCPUStatLine(t *testing.T) {
	stat, err := ParseCPUStatLine("cpu  10 20 30 40 50 60 70 80")
	if err != nil {
		t.Fatalf("ParseCPUStatLine returned error: %v", err)
	}

	if stat.Idle != 90 {
		t.Fatalf("idle = %d, want 90", stat.Idle)
	}
	if stat.Total != 360 {
		t.Fatalf("total = %d, want 360", stat.Total)
	}
}

func TestParseCPUStatLineRejectsMalformedInput(t *testing.T) {
	tests := []string{
		"",
		"intr 1 2 3 4",
		"cpu 1 2 nope 4",
	}

	for _, test := range tests {
		if _, err := ParseCPUStatLine(test); err == nil {
			t.Fatalf("ParseCPUStatLine(%q) returned nil error", test)
		}
	}
}

func TestUsagePercent(t *testing.T) {
	usage, ok := UsagePercent(
		CPUStat{Idle: 100, Total: 200},
		CPUStat{Idle: 125, Total: 300},
	)
	if !ok {
		t.Fatal("UsagePercent returned ok=false")
	}

	if math.Abs(usage-75) > 0.0001 {
		t.Fatalf("usage = %f, want 75", usage)
	}
}

func TestUsagePercentRejectsNonIncreasingCounters(t *testing.T) {
	_, ok := UsagePercent(
		CPUStat{Idle: 100, Total: 200},
		CPUStat{Idle: 100, Total: 200},
	)
	if ok {
		t.Fatal("UsagePercent returned ok=true")
	}
}
