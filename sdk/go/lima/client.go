// Package lima provides a Go client for the LiMa API.
package lima

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ClientConfig configures the LiMa client.
type ClientConfig struct {
	APIKey     string
	BaseURL    string
	HTTPClient *http.Client
}

// Client is the LiMa API client.
type Client struct {
	apiKey  string
	baseURL string
	http    *http.Client

	Chat    *ChatService
	Images  *ImagesService
	Devices *DevicesService
	Assets  *AssetsService
}

// NewClient creates a new LiMa client.
func NewClient(cfg ClientConfig) *Client {
	baseURL := cfg.BaseURL
	if baseURL == "" {
		baseURL = "https://chat.donglicao.com"
	}
	httpClient := cfg.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 60 * time.Second}
	}
	c := &Client{
		apiKey:  cfg.APIKey,
		baseURL: baseURL,
		http:    httpClient,
	}
	c.Chat = &ChatService{client: c}
	c.Images = &ImagesService{client: c}
	c.Devices = &DevicesService{client: c}
	c.Assets = &AssetsService{client: c}
	return c
}

func (c *Client) request(ctx context.Context, method, path string, body any) (*http.Response, error) {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		bodyReader = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return c.http.Do(req)
}

func (c *Client) jsonRequest(ctx context.Context, method, path string, body any, out any) error {
	resp, err := c.request(ctx, method, path, body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if err := checkResponse(resp); err != nil {
		return err
	}
	if out != nil {
		return json.NewDecoder(resp.Body).Decode(out)
	}
	return nil
}

func checkResponse(resp *http.Response) error {
	if resp.StatusCode < 300 {
		return nil
	}
	data, _ := io.ReadAll(resp.Body)
	var body map[string]any
	_ = json.Unmarshal(data, &body)
	message := extractMessage(body, resp.Status)
	code := extractCode(body)
	return &LiMaAPIError{
		StatusCode:   resp.StatusCode,
		Code:         code,
		ResponseBody: body,
		Message:      message,
	}
}

func extractMessage(body map[string]any, fallback string) string {
	if m, ok := body["message"].(string); ok {
		return m
	}
	if err, ok := body["error"].(map[string]any); ok {
		if m, ok := err["message"].(string); ok {
			return m
		}
	}
	return fallback
}

func extractCode(body map[string]any) string {
	if c, ok := body["code"].(string); ok {
		return c
	}
	if err, ok := body["error"].(map[string]any); ok {
		if c, ok := err["type"].(string); ok {
			return c
		}
	}
	return ""
}

// APIErrorMessage is a helper to format an API error message.
func APIErrorMessage(err error) string {
	if apiErr, ok := err.(*LiMaAPIError); ok {
		return fmt.Sprintf("%d %s", apiErr.StatusCode, apiErr.Message)
	}
	return err.Error()
}
