# LiMa Go SDK

Official Go SDK for [LiMa](https://chat.donglicao.com).

## Install

```bash
go get github.com/donglicao/lima-sdk-go
```

## Quick start

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/donglicao/lima-sdk-go/lima"
)

func main() {
    client := lima.NewClient(lima.ClientConfig{APIKey: "sk-xxx"})
    resp, err := client.Chat.Create(context.Background(), lima.CreateChatCompletionRequest{
        Model: "lima-1.3",
        Messages: []lima.ChatMessage{
            {Role: "user", Content: "你好"},
        },
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(resp.Choices[0].Message.Content)
}
```

## Streaming

```go
chunks, errCh := client.Chat.CreateStream(ctx, req)
for chunk := range chunks {
    fmt.Print(chunk["choices"].([]any)[0].(map[string]any)["delta"].(map[string]any)["content"])
}
if err := <-errCh; err != nil {
    log.Fatal(err)
}
```

## Error handling

```go
if apiErr, ok := err.(*lima.LiMaAPIError); ok {
    fmt.Println(apiErr.StatusCode, apiErr.Message)
}
```
