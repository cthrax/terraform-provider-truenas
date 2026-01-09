package provider

import (
	"os"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"
	"github.com/hashicorp/terraform-plugin-go/tfprotov6"
)

// testAccProtoV6ProviderFactories are used to instantiate a provider during
// acceptance testing. The factory function will be invoked for every Terraform
// CLI command executed to create a provider server to which the CLI can
// reattach.
var testAccProtoV6ProviderFactories = map[string]func() (tfprotov6.ProviderServer, error){
	"truenas": providerserver.NewProtocol6WithError(New("test")()),
}

func testAccPreCheck(t *testing.T) {
	if os.Getenv("TF_ACC") == "" {
		t.Skip("Acceptance tests skipped unless env 'TF_ACC' set")
	}
	if v := os.Getenv("TRUENAS_HOST"); v == "" {
		t.Fatal("TRUENAS_HOST must be set for acceptance tests")
	}
	if v := os.Getenv("TRUENAS_TOKEN"); v == "" {
		t.Fatal("TRUENAS_TOKEN must be set for acceptance tests")
	}
}

func providerConfig() string {
	return `
provider "truenas" {
  host  = "` + os.Getenv("TRUENAS_HOST") + `"
  token = "` + os.Getenv("TRUENAS_TOKEN") + `"
}
`
}
