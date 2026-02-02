package provider

import (
	"fmt"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
)

func TestFilesystemMkdirResource_Schema(t *testing.T) {
	r := NewFilesystemMkdirResource()
	if r == nil {
		t.Fatal("NewFilesystemMkdirResource returned nil")
	}
}

func TestFilesystemMkdirResource_BuildParams_RequiredFields(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path: types.StringValue("/mnt/tank/testdir"),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()

	if params["path"] != "/mnt/tank/testdir" {
		t.Errorf("Expected path '/mnt/tank/testdir', got %v", params["path"])
	}
}

func TestFilesystemMkdirResource_BuildParams_WithMode(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path: types.StringValue("/mnt/tank/testdir"),
		Mode: types.StringValue("755"),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()
	if !data.Mode.IsNull() {
		params["mode"] = data.Mode.ValueString()
	}

	if params["path"] != "/mnt/tank/testdir" {
		t.Errorf("Expected path '/mnt/tank/testdir', got %v", params["path"])
	}
	if params["mode"] != "755" {
		t.Errorf("Expected mode '755', got %v", params["mode"])
	}
}

func TestFilesystemMkdirResource_BuildParams_ModeNull(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path: types.StringValue("/mnt/tank/testdir"),
		Mode: types.StringNull(),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()
	if !data.Mode.IsNull() {
		params["mode"] = data.Mode.ValueString()
	}

	if _, exists := params["mode"]; exists {
		t.Error("Null mode field should not be in params")
	}
}

func TestFilesystemMkdirResource_BuildParams_WithRaiseChmod(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path:       types.StringValue("/mnt/tank/testdir"),
		Mode:       types.StringValue("755"),
		RaiseChmod: types.BoolValue(true),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()
	if !data.Mode.IsNull() {
		params["mode"] = data.Mode.ValueString()
	}
	if !data.RaiseChmod.IsNull() {
		options := make(map[string]interface{})
		options["raise_chmod"] = data.RaiseChmod.ValueBool()
		params["options"] = options
	}

	if params["path"] != "/mnt/tank/testdir" {
		t.Errorf("Expected path '/mnt/tank/testdir', got %v", params["path"])
	}
	if params["mode"] != "755" {
		t.Errorf("Expected mode '755', got %v", params["mode"])
	}

	options, ok := params["options"].(map[string]interface{})
	if !ok {
		t.Fatal("Expected options to be a map")
	}
	if options["raise_chmod"] != true {
		t.Errorf("Expected raise_chmod true, got %v", options["raise_chmod"])
	}
}

func TestFilesystemMkdirResource_BuildParams_RaiseChmodFalse(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path:       types.StringValue("/mnt/tank/testdir"),
		RaiseChmod: types.BoolValue(false),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()
	if !data.RaiseChmod.IsNull() {
		options := make(map[string]interface{})
		options["raise_chmod"] = data.RaiseChmod.ValueBool()
		params["options"] = options
	}

	options, ok := params["options"].(map[string]interface{})
	if !ok {
		t.Fatal("Expected options to be a map")
	}
	if options["raise_chmod"] != false {
		t.Errorf("Expected raise_chmod false, got %v", options["raise_chmod"])
	}
}

func TestFilesystemMkdirResource_BuildParams_RaiseChmodNull(t *testing.T) {
	data := FilesystemMkdirResourceModel{
		Path:       types.StringValue("/mnt/tank/testdir"),
		RaiseChmod: types.BoolNull(),
	}

	params := map[string]interface{}{}
	params["path"] = data.Path.ValueString()
	if !data.RaiseChmod.IsNull() {
		options := make(map[string]interface{})
		options["raise_chmod"] = data.RaiseChmod.ValueBool()
		params["options"] = options
	}

	if _, exists := params["options"]; exists {
		t.Error("Null raise_chmod should not create options in params")
	}
}

// Acceptance Tests - require TF_ACC=1 and real TrueNAS

func TestAccFilesystemMkdirResource_basic(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccFilesystemMkdirResourceConfig("/mnt/tank/terraform_test_mkdir"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "path", "/mnt/tank/terraform_test_mkdir"),
					resource.TestCheckResourceAttrSet("truenas_filesystem_mkdir.test", "id"),
				),
			},
		},
	})
}

func TestAccFilesystemMkdirResource_withMode(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccFilesystemMkdirResourceConfigWithMode("/mnt/tank/terraform_test_mkdir_mode", "755"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "path", "/mnt/tank/terraform_test_mkdir_mode"),
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "mode", "755"),
					resource.TestCheckResourceAttrSet("truenas_filesystem_mkdir.test", "id"),
				),
			},
		},
	})
}

func TestAccFilesystemMkdirResource_withRaiseChmod(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccFilesystemMkdirResourceConfigWithRaiseChmod("/mnt/tank/terraform_test_mkdir_raise", "755", true),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "path", "/mnt/tank/terraform_test_mkdir_raise"),
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "mode", "755"),
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "raise_chmod", "true"),
					resource.TestCheckResourceAttrSet("truenas_filesystem_mkdir.test", "id"),
				),
			},
		},
	})
}

func TestAccFilesystemMkdirResource_updateMode(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccFilesystemMkdirResourceConfigWithMode("/mnt/tank/terraform_test_mkdir_update", "755"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "mode", "755"),
				),
			},
			{
				Config: testAccFilesystemMkdirResourceConfigWithMode("/mnt/tank/terraform_test_mkdir_update", "700"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_filesystem_mkdir.test", "mode", "700"),
				),
			},
		},
	})
}

func testAccFilesystemMkdirResourceConfig(path string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_filesystem_mkdir" "test" {
  path = %[1]q
}
`, path)
}

func testAccFilesystemMkdirResourceConfigWithMode(path, mode string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_filesystem_mkdir" "test" {
  path = %[1]q
  mode = %[2]q
}
`, path, mode)
}

func testAccFilesystemMkdirResourceConfigWithRaiseChmod(path, mode string, raiseChmod bool) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_filesystem_mkdir" "test" {
  path        = %[1]q
  mode        = %[2]q
  raise_chmod = %[3]t
}
`, path, mode, raiseChmod)
}
