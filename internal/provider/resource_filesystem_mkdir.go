package provider

import (
	"context"
	"fmt"

	"github.com/bmanojlovic/terraform-provider-truenas/internal/client"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

type FilesystemMkdirResource struct {
	client *client.Client
}

type FilesystemMkdirResourceModel struct {
	ID      types.String `tfsdk:"id"`
	Path    types.String `tfsdk:"path"`
	Mode    types.String `tfsdk:"mode"`
	Options types.Object `tfsdk:"options"`
}

type FilesystemMkdirOptions struct {
	RaiseChmod types.Bool `tfsdk:"raise_chmod"`
}

func NewFilesystemMkdirResource() resource.Resource {
	return &FilesystemMkdirResource{}
}

func (r *FilesystemMkdirResource) Metadata(ctx context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_filesystem_mkdir"
}

func (r *FilesystemMkdirResource) Schema(ctx context.Context, req resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		MarkdownDescription: "Create directory on TrueNAS filesystem",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Resource identifier (same as path)",
			},
			"path": schema.StringAttribute{
				Required:            true,
				MarkdownDescription: "Directory path to create on TrueNAS",
			},
			"mode": schema.StringAttribute{
				Optional:            true,
				MarkdownDescription: "Permissions mode (octal string, e.g., '755')",
			},
			"options": schema.SingleNestedAttribute{
				Optional:            true,
				MarkdownDescription: "Additional options for mkdir operation",
				Attributes: map[string]schema.Attribute{
					"raise_chmod": schema.BoolAttribute{
						Optional:            true,
						MarkdownDescription: "Raise error if chmod fails after directory creation",
					},
				},
			},
		},
	}
}

func (r *FilesystemMkdirResource) Configure(ctx context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	client, ok := req.ProviderData.(*client.Client)
	if !ok {
		resp.Diagnostics.AddError("Unexpected Resource Configure Type", "Expected *client.Client")
		return
	}
	r.client = client
}

func (r *FilesystemMkdirResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var data FilesystemMkdirResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Build request parameters
	params := map[string]interface{}{
		"path": data.Path.ValueString(),
	}

	// Add mode if specified
	if !data.Mode.IsNull() {
		params["mode"] = data.Mode.ValueString()
	}

	// Add options if specified
	if !data.Options.IsNull() {
		var options FilesystemMkdirOptions
		diags := data.Options.As(ctx, &options, types.ObjectAsOptions{})
		resp.Diagnostics.Append(diags...)
		if resp.Diagnostics.HasError() {
			return
		}

		optionsMap := make(map[string]interface{})
		if !options.RaiseChmod.IsNull() {
			optionsMap["raise_chmod"] = options.RaiseChmod.ValueBool()
		}
		if len(optionsMap) > 0 {
			params["options"] = optionsMap
		}
	}

	// Create directory
	_, err := r.client.Post("/api/v2.0/filesystem/mkdir", params)
	if err != nil {
		resp.Diagnostics.AddError("Create Directory Failed", fmt.Sprintf("Failed to create directory: %s", err.Error()))
		return
	}

	data.ID = types.StringValue(data.Path.ValueString())
	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *FilesystemMkdirResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var data FilesystemMkdirResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Verify directory still exists using filesystem.stat
	params := map[string]interface{}{
		"path": data.Path.ValueString(),
	}
	_, err := r.client.Post("/api/v2.0/filesystem/stat", params)
	if err != nil {
		// Directory doesn't exist anymore, remove from state
		resp.State.RemoveResource(ctx)
		return
	}

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *FilesystemMkdirResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var data FilesystemMkdirResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// If path changed, need to recreate
	var oldData FilesystemMkdirResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &oldData)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if data.Path.ValueString() != oldData.Path.ValueString() {
		resp.Diagnostics.AddError(
			"Path Change Not Supported",
			"Changing the directory path requires resource replacement. Use terraform apply with -replace flag.",
		)
		return
	}

	// Update permissions if mode changed
	if !data.Mode.IsNull() && data.Mode.ValueString() != oldData.Mode.ValueString() {
		params := map[string]interface{}{
			"path": data.Path.ValueString(),
			"mode": data.Mode.ValueString(),
		}
		_, err := r.client.Post("/api/v2.0/filesystem/setperm", params)
		if err != nil {
			resp.Diagnostics.AddError("Update Permissions Failed", fmt.Sprintf("Failed to update directory permissions: %s", err.Error()))
			return
		}
	}

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *FilesystemMkdirResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	// Optionally remove the directory - for now just remove from state
	// Uncomment below to actually delete the directory on destroy:
	/*
	var data FilesystemMkdirResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	params := map[string]interface{}{
		"path": data.Path.ValueString(),
	}
	_, err := r.client.Delete(fmt.Sprintf("/api/v2.0/filesystem/delete?path=%s", data.Path.ValueString()), params)
	if err != nil {
		resp.Diagnostics.AddError("Delete Directory Failed", fmt.Sprintf("Failed to delete directory: %s", err.Error()))
		return
	}
	*/
}
