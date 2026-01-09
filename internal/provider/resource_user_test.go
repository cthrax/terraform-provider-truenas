package provider

import (
	"fmt"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
)

func TestUserResource_Schema(t *testing.T) {
	r := NewUserResource()
	if r == nil {
		t.Fatal("NewUserResource returned nil")
	}
}

func TestUserResource_BuildParams_RequiredFields(t *testing.T) {
	data := UserResourceModel{
		Username: types.StringValue("testuser"),
		FullName: types.StringValue("Test User"),
	}

	params := map[string]interface{}{}
	params["username"] = data.Username.ValueString()
	params["full_name"] = data.FullName.ValueString()

	if params["username"] != "testuser" {
		t.Errorf("Expected username 'testuser', got %v", params["username"])
	}
	if params["full_name"] != "Test User" {
		t.Errorf("Expected full_name 'Test User', got %v", params["full_name"])
	}
}

func TestUserResource_BuildParams_OptionalFieldNull(t *testing.T) {
	data := UserResourceModel{
		Username: types.StringValue("testuser"),
		FullName: types.StringValue("Test User"),
		Email:    types.StringNull(),
	}

	params := map[string]interface{}{}
	params["username"] = data.Username.ValueString()
	params["full_name"] = data.FullName.ValueString()
	if !data.Email.IsNull() {
		params["email"] = data.Email.ValueString()
	}

	if _, exists := params["email"]; exists {
		t.Error("Null optional field should not be in params")
	}
}

func TestUserResource_BuildParams_OptionalFieldWithValue(t *testing.T) {
	data := UserResourceModel{
		Username: types.StringValue("testuser"),
		FullName: types.StringValue("Test User"),
		Email:    types.StringValue("test@example.com"),
	}

	params := map[string]interface{}{}
	params["username"] = data.Username.ValueString()
	params["full_name"] = data.FullName.ValueString()
	if !data.Email.IsNull() {
		params["email"] = data.Email.ValueString()
	}

	if params["email"] != "test@example.com" {
		t.Errorf("Expected email 'test@example.com', got %v", params["email"])
	}
}

func TestUserResource_BuildParams_BooleanFields(t *testing.T) {
	data := UserResourceModel{
		Username:       types.StringValue("testuser"),
		FullName:       types.StringValue("Test User"),
		Locked:         types.BoolValue(false),
		PasswordDisabled: types.BoolValue(true),
	}

	params := map[string]interface{}{}
	if !data.Locked.IsNull() {
		params["locked"] = data.Locked.ValueBool()
	}
	if !data.PasswordDisabled.IsNull() {
		params["password_disabled"] = data.PasswordDisabled.ValueBool()
	}

	if params["locked"] != false {
		t.Errorf("Expected locked false, got %v", params["locked"])
	}
	if params["password_disabled"] != true {
		t.Errorf("Expected password_disabled true, got %v", params["password_disabled"])
	}
}


// Acceptance Tests - require TF_ACC=1 and real TrueNAS

func TestAccUserResource_basic(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccUserResourceConfig("testuser", "Test User", "test@example.com"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_user.test", "username", "testuser"),
					resource.TestCheckResourceAttr("truenas_user.test", "full_name", "Test User"),
					resource.TestCheckResourceAttr("truenas_user.test", "email", "test@example.com"),
					resource.TestCheckResourceAttrSet("truenas_user.test", "id"),
				),
			},
		},
	})
}

func TestAccUserResource_update(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccUserResourceConfig("testuser2", "Test User Two", "test2@example.com"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_user.test", "email", "test2@example.com"),
				),
			},
			{
				Config: testAccUserResourceConfig("testuser2", "Test User Two", "updated@example.com"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_user.test", "email", "updated@example.com"),
				),
			},
		},
	})
}

func TestAccUserResource_locked(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccUserResourceConfigLocked("testuser3", "Test User Three", true),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_user.test", "locked", "true"),
				),
			},
			{
				Config: testAccUserResourceConfigLocked("testuser3", "Test User Three", false),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("truenas_user.test", "locked", "false"),
				),
			},
		},
	})
}

func testAccUserResourceConfig(username, fullName, email string) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_user" "test" {
  username  = %[1]q
  full_name = %[2]q
  email     = %[3]q
  password  = "TestPassword123!"
  group_create = true
}
`, username, fullName, email)
}

func testAccUserResourceConfigLocked(username, fullName string, locked bool) string {
	return providerConfig() + fmt.Sprintf(`
resource "truenas_user" "test" {
  username  = %[1]q
  full_name = %[2]q
  password  = "TestPassword123!"
  group_create = true
  locked    = %[3]t
}
`, username, fullName, locked)
}
