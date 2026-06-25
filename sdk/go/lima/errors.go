package lima

import "fmt"

// LiMaSDKError is the base SDK error.
type LiMaSDKError struct {
	Message string
}

func (e *LiMaSDKError) Error() string {
	return e.Message
}

// LiMaAPIError is returned when the LiMa API responds with a non-2xx status.
type LiMaAPIError struct {
	StatusCode   int
	Code         string
	ResponseBody map[string]any
	Message      string
}

func (e *LiMaAPIError) Error() string {
	return fmt.Sprintf("lima api error %d: %s", e.StatusCode, e.Message)
}
