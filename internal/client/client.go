package client

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	host           string
	token          string
	conn           *websocket.Conn
	httpClient     *http.Client
	mu             sync.Mutex
	reconnectMu    sync.Mutex
	requests       map[string]chan DDPResponse
	subscriptions  map[string]chan DDPEvent
	nextID         int
	connected      bool
	connGeneration int
}

type DDPEvent struct {
	Msg        string                 `json:"msg"`
	Collection string                 `json:"collection,omitempty"`
	ID         string                 `json:"id,omitempty"`
	Fields     map[string]interface{} `json:"fields,omitempty"`
}

type DDPMessage struct {
	Msg     string      `json:"msg"`
	Method  string      `json:"method,omitempty"`
	Params  interface{} `json:"params,omitempty"`
	ID      string      `json:"id,omitempty"`
	Version string      `json:"version,omitempty"`
	Support []string    `json:"support,omitempty"`
}

type DDPResponse struct {
	Msg     string      `json:"msg"`
	ID      string      `json:"id,omitempty"`
	Result  interface{} `json:"result,omitempty"`
	Error   interface{} `json:"error,omitempty"`
	Session string      `json:"session,omitempty"`
}

func NewClient(host, token string) (*Client, error) {
	return &Client{
		host:          host,
		token:         token,
		requests:      make(map[string]chan DDPResponse),
		subscriptions: make(map[string]chan DDPEvent),
		httpClient: &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
			},
			Timeout: 30 * time.Second,
		},
	}, nil
}

func (c *Client) connect() error {
	// Note: reconnectMu should be held by caller (ensureConnected)

	// Force HTTP/1.1 for WebSocket upgrade
	dialer := websocket.Dialer{
		HandshakeTimeout: 45 * time.Second,
		TLSClientConfig:  &tls.Config{InsecureSkipVerify: true},
	}

	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+c.token)

	url := fmt.Sprintf("wss://%s/websocket", c.host)
	conn, _, err := dialer.Dial(url, headers)
	if err != nil {
		return fmt.Errorf("websocket dial failed: %v", err)
	}

	c.mu.Lock()
	// Close old connection if exists - the old handleMessages will exit
	// but we increment connGeneration so it won't affect our state
	if c.conn != nil {
		_ = c.conn.Close()
	}
	// Clear pending requests
	for id, ch := range c.requests {
		close(ch)
		delete(c.requests, id)
	}
	c.conn = conn
	c.connGeneration++
	generation := c.connGeneration
	c.mu.Unlock()

	// Start message handler with current generation
	go c.handleMessages(generation)

	// Send DDP connect
	connectMsg := DDPMessage{
		Msg:     "connect",
		Version: "1",
		Support: []string{"1"},
	}

	if err := conn.WriteJSON(connectMsg); err != nil {
		c.mu.Lock()
		c.connected = false
		c.mu.Unlock()
		return fmt.Errorf("failed to send connect: %v", err)
	}

	// Wait for connected response
	time.Sleep(200 * time.Millisecond)

	// Authenticate
	c.mu.Lock()
	c.nextID++
	id := fmt.Sprintf("req%d", c.nextID)
	respChan := make(chan DDPResponse, 1)
	c.requests[id] = respChan
	c.mu.Unlock()

	authMsg := DDPMessage{
		Msg:    "method",
		Method: "auth.login_with_api_key",
		Params: []interface{}{c.token},
		ID:     id,
	}

	if err := conn.WriteJSON(authMsg); err != nil {
		c.mu.Lock()
		delete(c.requests, id)
		c.connected = false
		c.mu.Unlock()
		return fmt.Errorf("failed to send auth: %v", err)
	}

	select {
	case authResp := <-respChan:
		log.Printf("Auth response: result=%v (type=%T), error=%v", authResp.Result, authResp.Result, authResp.Error)
		if result, ok := authResp.Result.(bool); !ok || !result {
			c.mu.Lock()
			c.connected = false
			c.mu.Unlock()
			return fmt.Errorf("authentication failed: %v", authResp.Error)
		}
	case <-time.After(30 * time.Second):
		c.mu.Lock()
		delete(c.requests, id)
		c.connected = false
		c.mu.Unlock()
		return fmt.Errorf("authentication timeout")
	}

	c.mu.Lock()
	c.connected = true
	c.mu.Unlock()

	log.Println("WebSocket DDP connection established and authenticated")
	return nil
}

func (c *Client) handleMessages(generation int) {
	for {
		var msg map[string]interface{}
		if err := c.conn.ReadJSON(&msg); err != nil {
			c.mu.Lock()
			if c.connGeneration == generation {
				log.Printf("WebSocket read error: %v", err)
				c.connected = false
				if c.conn != nil {
					_ = c.conn.Close()
					c.conn = nil
				}
			}
			c.mu.Unlock()
			return
		}

		msgType, _ := msg["msg"].(string)

		// Handle method responses
		if msgType == "result" || msgType == "error" {
			if id, ok := msg["id"].(string); ok {
				c.mu.Lock()
				if ch, exists := c.requests[id]; exists {
					response := DDPResponse{
						Msg:    msgType,
						ID:     id,
						Result: msg["result"],
						Error:  msg["error"],
					}
					ch <- response
					delete(c.requests, id)
				}
				c.mu.Unlock()
			}
		}

		// Handle collection events (for subscriptions)
		if msgType == "changed" || msgType == "added" {
			collection, _ := msg["collection"].(string)
			id, _ := msg["id"].(string)
			fields, _ := msg["fields"].(map[string]interface{})

			event := DDPEvent{
				Msg:        msgType,
				Collection: collection,
				ID:         id,
				Fields:     fields,
			}

			c.mu.Lock()
			for _, ch := range c.subscriptions {
				select {
				case ch <- event:
				default:
				}
			}
			c.mu.Unlock()
		}
	}
}

func (c *Client) ensureConnected() error {
	c.mu.Lock()
	connected := c.connected && c.conn != nil
	c.mu.Unlock()

	if connected {
		return nil
	}

	// Serialize reconnection attempts
	c.reconnectMu.Lock()
	defer c.reconnectMu.Unlock()

	// Check again after acquiring lock - another goroutine may have reconnected
	c.mu.Lock()
	connected = c.connected && c.conn != nil
	c.mu.Unlock()

	if connected {
		return nil
	}

	log.Println("Reconnecting...")
	return c.connect()
}

// InitialConnect establishes the initial connection during provider setup
func (c *Client) InitialConnect() error {
	c.reconnectMu.Lock()
	defer c.reconnectMu.Unlock()
	return c.connect()
}

func (c *Client) call(method string, params interface{}) (*DDPResponse, error) {
	if err := c.ensureConnected(); err != nil {
		return nil, err
	}

	c.mu.Lock()
	c.nextID++
	id := fmt.Sprintf("req%d", c.nextID)
	respChan := make(chan DDPResponse, 1)
	c.requests[id] = respChan

	msg := DDPMessage{
		Msg:    "method",
		Method: method,
		Params: params,
		ID:     id,
	}

	if err := c.conn.WriteJSON(msg); err != nil {
		delete(c.requests, id)
		c.mu.Unlock()
		return nil, fmt.Errorf("failed to send message: %v", err)
	}
	c.mu.Unlock()

	select {
	case response := <-respChan:
		return &response, nil
	case <-time.After(30 * time.Second):
		c.mu.Lock()
		delete(c.requests, id)
		c.mu.Unlock()
		return nil, fmt.Errorf("request timeout")
	}
}

func (c *Client) Call(method string, params interface{}) (interface{}, error) {
	// For DDP protocol, params should be wrapped in array unless already an array
	var ddpParams interface{}
	
	// Check if params is already an array
	if _, isSlice := params.([]interface{}); isSlice {
		// Already an array, use as-is
		ddpParams = params
	} else {
		switch method {
		case "vm.update", "vm.stop", "vm.device.update", "pool.dataset.delete", "pool.dataset.update", "pool.snapshot.delete", "core.subscribe":
			// These expect params as-is (already in correct format)
			ddpParams = params
		case "vm.delete", "vm.get_instance":
			// These expect integer ID parameter
			if idStr, ok := params.(string); ok {
				// Convert string ID to integer
				if id, err := strconv.Atoi(idStr); err == nil {
					ddpParams = []interface{}{id}
				} else {
					return nil, fmt.Errorf("invalid ID format: %s", idStr)
				}
			} else {
				ddpParams = []interface{}{params}
			}
		default:
			// vm.create and others expect [data] format
			ddpParams = []interface{}{params}
		}
	}

	response, err := c.call(method, ddpParams)
	if err != nil {
		return nil, err
	}

	if response.Error != nil {
		cleanErr := formatTrueNASError(response.Error)
		// Store full error for debug access
		fullErr := fmt.Sprintf("%v", response.Error)
		if cleanErr != fullErr {
			// Log full error for debugging
			log.Printf("[DEBUG] TrueNAS API full error: %s", fullErr)
		}
		return nil, fmt.Errorf("%s failed: %s", method, cleanErr)
	}

	return response.Result, nil
}

// formatTrueNASError extracts the meaningful error message from TrueNAS error response
func formatTrueNASError(err interface{}) string {
	errMap, ok := err.(map[string]interface{})
	if !ok {
		return fmt.Sprintf("%v", err)
	}
	
	// Extract the main error reason
	if reason, ok := errMap["reason"].(string); ok && reason != "" {
		return reason
	}
	
	// Extract validation errors from extra field
	if extra, ok := errMap["extra"].([]interface{}); ok && len(extra) > 0 {
		if extraList, ok := extra[0].([]interface{}); ok && len(extraList) > 1 {
			// Format: [field, message, code]
			if len(extraList) >= 2 {
				field := fmt.Sprintf("%v", extraList[0])
				msg := fmt.Sprintf("%v", extraList[1])
				return fmt.Sprintf("%s: %s", field, msg)
			}
		}
	}
	
	// Fallback to full error
	return fmt.Sprintf("%v", err)
}

// CallWithJob calls a method that returns a job ID and waits for completion
func (c *Client) CallWithJob(method string, params interface{}) (interface{}, error) {
	result, err := c.Call(method, params)
	if err != nil {
		return nil, err
	}

	// Result should be a job ID (integer)
	var jobID int
	switch v := result.(type) {
	case float64:
		jobID = int(v)
	case int:
		jobID = v
	default:
		// Not a job, return result directly
		return result, nil
	}

	// Wait for job completion
	jobResult, err := c.call("core.job_wait", []interface{}{jobID})
	if err != nil {
		return nil, fmt.Errorf("job wait failed: %v", err)
	}

	if jobResult.Error != nil {
		return nil, fmt.Errorf("job %d failed: %v", jobID, jobResult.Error)
	}

	return jobResult.Result, nil
}

// UploadFile performs a multipart file upload to the specified endpoint
func (c *Client) UploadFile(endpoint string, jsonData map[string]interface{}, fileContent []byte, filename string) (interface{}, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	// Add JSON data part
	jsonBytes, err := json.Marshal(jsonData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal JSON data: %v", err)
	}
	if err := writer.WriteField("data", string(jsonBytes)); err != nil {
		return nil, fmt.Errorf("failed to write data field: %v", err)
	}

	// Add file part
	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, fmt.Errorf("failed to create form file: %v", err)
	}
	if _, err := io.Copy(part, bytes.NewReader(fileContent)); err != nil {
		return nil, fmt.Errorf("failed to write file content: %v", err)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("failed to close multipart writer: %v", err)
	}

	// Create HTTP request
	url := fmt.Sprintf("https://%s%s", c.host, endpoint)
	req, err := http.NewRequest("POST", url, &buf)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("Authorization", "Bearer "+c.token)

	// Execute request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %v", err)
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	var result interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %v", err)
	}

	return result, nil
}

func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// JobResult contains the final state of a completed job
type JobResult struct {
	ID       int
	State    string
	Result   interface{}
	Progress float64
	Error    string
}

// WaitForJob subscribes to job events and waits for completion
func (c *Client) WaitForJob(jobID int, timeout time.Duration) (*JobResult, error) {
	// Subscribe to job updates
	subID := fmt.Sprintf("job_%d", jobID)
	eventChan := make(chan DDPEvent, 10)

	c.mu.Lock()
	c.subscriptions[subID] = eventChan
	c.mu.Unlock()

	defer func() {
		c.mu.Lock()
		delete(c.subscriptions, subID)
		c.mu.Unlock()
		close(eventChan)
	}()

	// Subscribe to core.get_jobs events
	// Use raw call() to avoid parameter wrapping
	resp, err := c.call("core.subscribe", []interface{}{"core.get_jobs"})
	if err != nil {
		return nil, fmt.Errorf("failed to subscribe to jobs: %v", err)
	}
	if resp.Error != nil {
		return nil, fmt.Errorf("subscribe failed: %v", resp.Error)
	}

	// Wait for job completion
	deadline := time.Now().Add(timeout)
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case event := <-eventChan:
			if event.Collection == "core.get_jobs" {
				// Check if this event is for our job
				eventJobID := 0
				if idField, ok := event.Fields["id"].(float64); ok {
					eventJobID = int(idField)
				} else if idField, ok := event.Fields["id"].(int); ok {
					eventJobID = idField
				}
				
				if eventJobID != jobID {
					continue // Not our job, skip
				}
				
				state, _ := event.Fields["state"].(string)
				progress, _ := event.Fields["progress"].(map[string]interface{})
				progressPct := 0.0
				if progress != nil {
					if pct, ok := progress["percent"].(float64); ok {
						progressPct = pct
					}
				}

				log.Printf("Job %d: state=%s progress=%.1f%%", jobID, state, progressPct)

				if state == "SUCCESS" {
					return &JobResult{
						ID:       jobID,
						State:    state,
						Result:   event.Fields["result"],
						Progress: progressPct,
					}, nil
				}

				if state == "FAILED" || state == "ABORTED" {
					errMsg := ""
					if errField, ok := event.Fields["error"].(string); ok {
						errMsg = errField
					}
					return &JobResult{
						ID:       jobID,
						State:    state,
						Progress: progressPct,
						Error:    errMsg,
					}, fmt.Errorf("job failed: %s", errMsg)
				}
			}

		case <-ticker.C:
			if time.Now().After(deadline) {
				return nil, fmt.Errorf("job timeout after %v", timeout)
			}

		case <-time.After(timeout):
			return nil, fmt.Errorf("job timeout")
		}
	}
}
