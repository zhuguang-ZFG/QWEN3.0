package lima

import "context"

// ImageGeneration is the response from the image generation endpoint.
type ImageGeneration struct {
	Data []struct {
		URL     string `json:"url,omitempty"`
		B64JSON string `json:"b64_json,omitempty"`
	} `json:"data"`
}

// CreateImageRequest is the request body for image generation.
type CreateImageRequest struct {
	Model  string `json:"model"`
	Prompt string `json:"prompt"`
	Size   string `json:"size,omitempty"`
	N      int    `json:"n,omitempty"`
}

// ImagesService provides image generation.
type ImagesService struct {
	client *Client
}

// Generate creates an image from a prompt.
func (s *ImagesService) Generate(ctx context.Context, req CreateImageRequest) (*ImageGeneration, error) {
	var resp ImageGeneration
	if err := s.client.jsonRequest(ctx, "POST", "/v1/images/generations", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}
