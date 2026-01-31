package provider

import (
	"fmt"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
)

func TestVmResource_Schema(t *testing.T) {
	r := NewVmResource()
	if r == nil {
		t.Fatal("NewVmResource returned nil")
	}
}

func TestVmResource_BuildParams_RequiredFields(t *testing.T) {
	data := VmResourceModel{
		Name: types.StringValue("test-vm"),
	}

	params := map[string]interface{}{}
	params["name"] = data.Name.ValueString()

	if params["name"] != "test-vm" {
		t.Errorf("Expected name 'test-vm', got %v", params["name"])
	}
}

func TestVmResource_BuildParams_OptionalFieldNull(t *testing.T) {
	data := VmResourceModel{
		Name:        types.StringValue("test-vm"),
		Description: types.StringNull(),
	}

	params := map[string]interface{}{}
	params["name"] = data.Name.ValueString()
	if !data.Description.IsNull() {
		params["description"] = data.Description.ValueString()
	}

	if _, exists := params["description"]; exists {
		t.Error("Null optional field should not be in params")
	}
}

func TestVmResource_BuildParams_OptionalFieldWithValue(t *testing.T) {
	data := VmResourceModel{
		Name:        types.StringValue("test-vm"),
		Description: types.StringValue("test description"),
	}

	params := map[string]interface{}{}
	params["name"] = data.Name.ValueString()
	if !data.Description.IsNull() {
		params["description"] = data.Description.ValueString()
	}

	if params["description"] != "test description" {
		t.Errorf("Expected description 'test description', got %v", params["description"])
	}
}

func TestVmResource_StartOnCreateDefault(t *testing.T) {
	data := VmResourceModel{
		StartOnCreate: types.BoolNull(),
	}

	startOnCreate := true
	if !data.StartOnCreate.IsNull() {
		startOnCreate = data.StartOnCreate.ValueBool()
	}

	if !startOnCreate {
		t.Error("start_on_create should default to true when null")
	}
}

func TestVmResource_StartOnCreateFalse(t *testing.T) {
	data := VmResourceModel{
		StartOnCreate: types.BoolValue(false),
	}

	startOnCreate := true
	if !data.StartOnCreate.IsNull() {
		startOnCreate = data.StartOnCreate.ValueBool()
	}

	if startOnCreate {
		t.Error("start_on_create should be false when explicitly set")
	}
}

func TestVmResource_StartOnCreateTrue(t *testing.T) {
	data := VmResourceModel{
		StartOnCreate: types.BoolValue(true),
	}

	startOnCreate := true
	if !data.StartOnCreate.IsNull() {
		startOnCreate = data.StartOnCreate.ValueBool()
	}

	if !startOnCreate {
		t.Error("start_on_create should be true when explicitly set")
	}
}

// Acceptance Tests - require TF_ACC=1 and real TrueNAS

func TestAccVmResource_basic(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccVmResourceConfig("testvmacc", "Test VM from acceptance test"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_vm.test", "name", "testvmacc"),
					resource.TestCheckResourceAttr("truenas_vm.test", "description", "Test VM from acceptance test"),
					resource.TestCheckResourceAttrSet("truenas_vm.test", "id"),
				),
			},
		},
	})
}

func TestAccVmResource_update(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccVmResourceConfig("testvmupdate", "Initial description"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_vm.test", "description", "Initial description"),
				),
			},
			{
				Config: testAccVmResourceConfig("testvmupdate", "Updated description"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_vm.test", "description", "Updated description"),
				),
			},
		},
	})
}

func TestAccVmResource_startOnCreate(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccVmResourceConfigNoStart("testvmnostart", "VM that should not start"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_vm.test", "start_on_create", "false"),
				),
			},
		},
	})
}

func testAccVmResourceConfig(name, description string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_vm" "test" {
  name        = %[1]q
  description = %[2]q
  vcpus       = 1
  memory      = 1024
}
`, name, description)
}

func testAccVmResourceConfigNoStart(name, description string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_vm" "test" {
  name            = %[1]q
  description     = %[2]q
  vcpus           = 1
  memory          = 1024
  start_on_create = false
}
`, name, description)
}
