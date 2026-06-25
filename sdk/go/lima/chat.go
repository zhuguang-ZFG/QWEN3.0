package lima

import (
	"bufio"
	"context"
	"encoding/json"
	"strings"
)

// ChatMessage mirrors the OpenAI chat message shape.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatCompletion is a non-streaming chat completion response.
type ChatCompletion struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Choices []struct {
		Message      ChatMessage `json:"message"`
		FinishReason string      `json:"finish_reason"`
	} `json:"choices"`
}

// ChatCompletionChunk is a single SSE chunk.
type ChatCompletionChunk map[string]any

// ChatService provides chat completions.
type ChatService struct {
	client *Client
}

// Create sends a chat completion request.
func (s *ChatService) Create(ctx context.Context, req CreateChatCompletionRequest) (*ChatCompletion, error) {
	var resp ChatCompletion
	if err := s.client.jsonRequest(ctx, "POST", "/v1/chat/completions", req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// CreateStream sends a streaming chat completion request.
func (s *ChatService) CreateStream(ctx context.Context, req CreateChatCompletionRequest) (<-chan ChatCompletionChunk, <-chan error) {
	out := make(chan ChatCompletionChunk)
	errCh := make(chan error, 1)
	req.Stream = true

	go func() {
		defer close(out)
		defer close(errCh)
		resp, err := s.client.request(ctx, "POST", "/v1/chat/completions", req)
		if err != nil {
			errCh <- err
			return
		}
		defer resp.Body.Close()
		if err := checkResponse(resp); err != nil {
			errCh <- err
			return
		}
		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			chunk, ok := parseSSELine(line)
			if !ok {
				continue
			}
			select {
			case out <- chunk:
			case <-ctx.Done():
				errCh <- ctx.Err()
				return
			}
		}
		if err := scanner.Err(); err != nil {
			errCh <- err
		}
	}()

	return out, errCh
}

// CreateChatCompletionRequest is the request body for chat completions.
type CreateChatCompletionRequest struct {
	Model    string        `json:"model"`
	Messages []ChatMessage `json:"messages"`
	Stream   bool          `json:"stream,omitempty"`
}

func parseSSELine(line string) (ChatCompletionChunk, bool) {
	trimmed := strings.TrimSpace(line)
	if !strings.HasPrefix(trimmed, "data: ") {
		return nil, false
	}
	payload := strings.TrimSpace(trimmed[len("data: "):])
	if payload == "[DONE]" || payload == "" {
		return nil, false
	}
	var chunk ChatCompletionChunk
	if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
		return nil, false
	}
	return chunk, true
}
