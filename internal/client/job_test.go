package client

import (
	"testing"
	"time"
)

func TestWaitForJob(t *testing.T) {
	t.Skip("Requires live TrueNAS instance")

	client, err := NewClient("192.168.1.100", "your-token")
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer func() {
		_ = client.Close()
	}()

	if err := client.InitialConnect(); err != nil {
		t.Fatalf("Failed to connect: %v", err)
	}

	// Trigger a pool scrub (background job)
	result, err := client.Call("pool.scrub", map[string]interface{}{
		"pool":   "tank",
		"action": "START",
	})
	if err != nil {
		t.Fatalf("Failed to start scrub: %v", err)
	}

	jobID, ok := result.(float64)
	if !ok {
		t.Fatalf("Expected job ID, got: %v", result)
	}

	t.Logf("Started job %d", int(jobID))

	// Wait for job completion
	jobResult, err := client.WaitForJob(int(jobID), 5*time.Minute)
	if err != nil {
		t.Fatalf("Job failed: %v", err)
	}

	t.Logf("Job completed: state=%s progress=%.1f%%", jobResult.State, jobResult.Progress)

	if jobResult.State != "SUCCESS" {
		t.Errorf("Expected SUCCESS, got %s", jobResult.State)
	}
}
