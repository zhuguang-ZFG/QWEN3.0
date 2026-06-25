package lima

import "context"

// Asset represents an asset library item.
type Asset map[string]any

// AssetsService manages the asset library.
type AssetsService struct {
	client *Client
}

// List returns assets matching the provided filters.
func (s *AssetsService) List(ctx context.Context, params map[string]string) ([]Asset, error) {
	path := "/device/v1/app/assets"
	if len(params) > 0 {
		path += "?"
		first := true
		for k, v := range params {
			if !first {
				path += "&"
			}
			first = false
			path += k + "=" + v
		}
	}
	var result struct {
		Assets []Asset `json:"assets"`
	}
	if err := s.client.jsonRequest(ctx, "GET", path, nil, &result); err != nil {
		return nil, err
	}
	return result.Assets, nil
}

// Create uploads a new asset.
func (s *AssetsService) Create(ctx context.Context, body map[string]any) (Asset, error) {
	var asset Asset
	if err := s.client.jsonRequest(ctx, "POST", "/device/v1/app/assets", body, &asset); err != nil {
		return nil, err
	}
	return asset, nil
}
