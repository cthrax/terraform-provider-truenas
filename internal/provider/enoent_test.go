package provider

import (
	"strings"
	"testing"
)

// TestENOENTDetection verifies that only [ENOENT] errors trigger resource removal
func TestENOENTDetection(t *testing.T) {
	tests := []struct {
		name           string
		errorMsg       string
		shouldRemove   bool
	}{
		{
			name:         "ENOENT error should remove resource",
			errorMsg:     "[ENOENT] None: Certificate 3 does not exist",
			shouldRemove: true,
		},
		{
			name:         "ENOENT with different resource",
			errorMsg:     "[ENOENT] VM 5 does not exist",
			shouldRemove: true,
		},
		{
			name:         "Parent does not exist should NOT remove",
			errorMsg:     "[EINVAL] Parent pool does not exist",
			shouldRemove: false,
		},
		{
			name:         "Referenced user does not exist should NOT remove",
			errorMsg:     "[EINVAL] Referenced user does not exist",
			shouldRemove: false,
		},
		{
			name:         "Generic does not exist without ENOENT should NOT remove",
			errorMsg:     "Resource does not exist",
			shouldRemove: false,
		},
		{
			name:         "Permission error should NOT remove",
			errorMsg:     "[EPERM] Permission denied",
			shouldRemove: false,
		},
		{
			name:         "Validation error should NOT remove",
			errorMsg:     "[EINVAL] Invalid parameter",
			shouldRemove: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// This mirrors the logic in the generated Read function
			shouldRemove := strings.Contains(tt.errorMsg, "[ENOENT]")
			
			if shouldRemove != tt.shouldRemove {
				t.Errorf("Error %q: got shouldRemove=%v, want %v", tt.errorMsg, shouldRemove, tt.shouldRemove)
			}
		})
	}
}
