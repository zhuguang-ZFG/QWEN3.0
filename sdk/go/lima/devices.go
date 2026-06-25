package lima

import (
	"context"
	"fmt"
)

// Device represents a device returned by the API.
type Device map[string]any

// Task represents a device task returned by the API.
type Task map[string]any

// DevicesService manages devices and tasks.
type DevicesService struct {
	client *Client
}

// List returns all devices bound to the account.
func (s *DevicesService) List(ctx context.Context) ([]Device, error) {
	var result struct {
		Devices []Device `json:"devices"`
	}
	if err := s.client.jsonRequest(ctx, "GET", "/device/v1/app/devices", nil, &result); err != nil {
		return nil, err
	}
	return result.Devices, nil
}

// Get returns a single device by ID.
func (s *DevicesService) Get(ctx context.Context, deviceID string) (Device, error) {
	var dev Device
	if err := s.client.jsonRequest(ctx, "GET", fmt.Sprintf("/device/v1/app/devices/%s", deviceID), nil, &dev); err != nil {
		return nil, err
	}
	return dev, nil
}

// Status returns the runtime status of a device.
func (s *DevicesService) Status(ctx context.Context, deviceID string) (map[string]any, error) {
	var status map[string]any
	if err := s.client.jsonRequest(ctx, "GET", fmt.Sprintf("/device/v1/app/devices/%s/status", deviceID), nil, &status); err != nil {
		return nil, err
	}
	return status, nil
}

// CreateTask creates a task on a device.
func (s *DevicesService) CreateTask(ctx context.Context, deviceID string, body map[string]any) (Task, error) {
	var task Task
	path := fmt.Sprintf("/device/v1/app/devices/%s/tasks", deviceID)
	if err := s.client.jsonRequest(ctx, "POST", path, body, &task); err != nil {
		return nil, err
	}
	return task, nil
}

// ListTasks returns tasks for a device.
func (s *DevicesService) ListTasks(ctx context.Context, deviceID string, params map[string]string) ([]Task, error) {
	path := "/device/v1/app/tasks?device_id=" + deviceID
	for k, v := range params {
		path += "&" + k + "=" + v
	}
	var result struct {
		Tasks []Task `json:"tasks"`
	}
	if err := s.client.jsonRequest(ctx, "GET", path, nil, &result); err != nil {
		return nil, err
	}
	return result.Tasks, nil
}

// GetTask returns a single task by ID.
func (s *DevicesService) GetTask(ctx context.Context, taskID string) (Task, error) {
	var task Task
	if err := s.client.jsonRequest(ctx, "GET", fmt.Sprintf("/device/v1/app/tasks/%s", taskID), nil, &task); err != nil {
		return nil, err
	}
	return task, nil
}
