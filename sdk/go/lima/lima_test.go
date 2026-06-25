package lima

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func newTestClient(handler http.HandlerFunc) (*Client, *httptest.Server) {
	server := httptest.NewServer(handler)
	client := NewClient(ClientConfig{APIKey: "sk-test", BaseURL: server.URL})
	return client, server
}

func TestChatCreate(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Path != "/v1/chat/completions" {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		json.NewEncoder(w).Encode(ChatCompletion{
			ID: "chat-1",
			Choices: []struct {
				Message      ChatMessage `json:"message"`
				FinishReason string      `json:"finish_reason"`
			}{{Message: ChatMessage{Role: "assistant", Content: "hello"}}},
		})
	})
	defer server.Close()

	resp, err := client.Chat.Create(context.Background(), CreateChatCompletionRequest{
		Model:    "lima-1.3",
		Messages: []ChatMessage{{Role: "user", Content: "hi"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Choices[0].Message.Content != "hello" {
		t.Fatalf("unexpected content: %s", resp.Choices[0].Message.Content)
	}
}

func TestChatCreateStream(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, "data: {\"choices\":[{\"delta\":{\"content\":\"hi\"}}]}\n")
		fmt.Fprint(w, "data: {\"choices\":[{\"delta\":{\"content\":\"!\"}}]}\n")
		fmt.Fprint(w, "data: [DONE]\n")
	})
	defer server.Close()

	chunks, errCh := client.Chat.CreateStream(context.Background(), CreateChatCompletionRequest{
		Model:    "lima-1.3",
		Messages: []ChatMessage{{Role: "user", Content: "hi"}},
	})
	count := 0
	for range chunks {
		count++
	}
	if err := <-errCh; err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Fatalf("expected 2 chunks, got %d", count)
	}
}

func TestImagesGenerate(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(ImageGeneration{Data: []struct {
			URL     string `json:"url,omitempty"`
			B64JSON string `json:"b64_json,omitempty"`
		}{{URL: "https://example.com/img.png"}}})
	})
	defer server.Close()

	resp, err := client.Images.Generate(context.Background(), CreateImageRequest{Model: "dall-e-3", Prompt: "a cat"})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Data[0].URL != "https://example.com/img.png" {
		t.Fatalf("unexpected url: %s", resp.Data[0].URL)
	}
}

func TestDevicesListAndStatus(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/device/v1/app/devices":
			json.NewEncoder(w).Encode(map[string]any{"devices": []any{map[string]any{"deviceId": "d1"}}})
		case "/device/v1/app/devices/d1/status":
			json.NewEncoder(w).Encode(map[string]any{"online": true})
		default:
			http.Error(w, "not found", http.StatusNotFound)
		}
	})
	defer server.Close()

	devices, err := client.Devices.List(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if devices[0]["deviceId"] != "d1" {
		t.Fatalf("unexpected device id: %v", devices[0]["deviceId"])
	}
	status, err := client.Devices.Status(context.Background(), "d1")
	if err != nil {
		t.Fatal(err)
	}
	if status["online"] != true {
		t.Fatalf("unexpected status: %v", status["online"])
	}
}

func TestDevicesCreateAndGetTask(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/device/v1/app/devices/d1/tasks":
			json.NewEncoder(w).Encode(map[string]any{"taskId": "t1"})
		case "/device/v1/app/tasks/t1":
			json.NewEncoder(w).Encode(map[string]any{"taskId": "t1", "status": "running"})
		default:
			http.Error(w, "not found", http.StatusNotFound)
		}
	})
	defer server.Close()

	task, err := client.Devices.CreateTask(context.Background(), "d1", map[string]any{"text": "hello"})
	if err != nil {
		t.Fatal(err)
	}
	if task["taskId"] != "t1" {
		t.Fatalf("unexpected task id: %v", task["taskId"])
	}
	fetched, err := client.Devices.GetTask(context.Background(), "t1")
	if err != nil {
		t.Fatal(err)
	}
	if fetched["status"] != "running" {
		t.Fatalf("unexpected status: %v", fetched["status"])
	}
}

func TestAssetsListAndCreate(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/device/v1/app/assets":
			if r.Method == "GET" {
				json.NewEncoder(w).Encode(map[string]any{"assets": []any{map[string]any{"assetId": "a1"}}})
			} else {
				json.NewEncoder(w).Encode(map[string]any{"assetId": "a2"})
			}
		default:
			http.Error(w, "not found", http.StatusNotFound)
		}
	})
	defer server.Close()

	assets, err := client.Assets.List(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if assets[0]["assetId"] != "a1" {
		t.Fatalf("unexpected asset id: %v", assets[0]["assetId"])
	}
	created, err := client.Assets.Create(context.Background(), map[string]any{"title": "cat", "category": "svg", "content": "<svg/>"})
	if err != nil {
		t.Fatal(err)
	}
	if created["assetId"] != "a2" {
		t.Fatalf("unexpected asset id: %v", created["assetId"])
	}
}

func TestAPIError(t *testing.T) {
	client, server := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]any{"error": map[string]any{"message": "not found", "type": "not_found"}})
	})
	defer server.Close()

	_, err := client.Devices.Get(context.Background(), "missing")
	apiErr, ok := err.(*LiMaAPIError)
	if !ok {
		t.Fatalf("expected LiMaAPIError, got %T", err)
	}
	if apiErr.StatusCode != 404 {
		t.Fatalf("expected 404, got %d", apiErr.StatusCode)
	}
}
