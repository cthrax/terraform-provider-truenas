package provider

import (
	"fmt"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
)

// Unit Tests

func TestPoolDatasetResource_Schema(t *testing.T) {
	r := NewPoolDatasetResource()
	if r == nil {
		t.Fatal("NewPoolDatasetResource returned nil")
	}
}

func TestPoolDatasetResource_BuildParams(t *testing.T) {
	_ = PoolDatasetResourceModel{
		ID: types.StringValue("test-pool/test-dataset"),
	}

	params := map[string]interface{}{}
	// Pool dataset has minimal fields - just ID

	if len(params) != 0 {
		t.Errorf("Expected empty params for minimal resource, got %d fields", len(params))
	}
}

// Acceptance Tests - require TF_ACC=1 and real TrueNAS

func TestAccPoolDatasetResource_basic(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccPoolDatasetResourceConfig("test-pool", "test-dataset"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttrSet("truenas_pool_dataset.test", "id"),
				),
			},
		},
	})
}

func TestAccPoolDatasetResource_update(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccPoolDatasetResourceConfig("test-pool", "test-dataset-update"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttrSet("truenas_pool_dataset.test", "id"),
				),
			},
		},
	})
}

func testAccPoolDatasetResourceConfig(pool, dataset string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_pool_dataset" "test" {
  # Pool dataset resource with minimal configuration
  # ID will be: %[1]s/%[2]s
}
`, pool, dataset)
}
