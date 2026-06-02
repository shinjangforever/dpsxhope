// llm_client.go — LLM API client in Go
// เหมาะกับ production service ที่ต้องการ throughput สูง + memory ต่ำ
//
// รัน: go run llm_client.go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const anthropicURL = "https://api.anthropic.com/v1/messages"

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type Request struct {
	Model     string    `json:"model"`
	MaxTokens int       `json:"max_tokens"`
	System    string    `json:"system"`
	Messages  []Message `json:"messages"`
}

type Response struct {
	Content []struct {
		Text string `json:"text"`
	} `json:"content"`
	Usage struct {
		InputTokens  int `json:"input_tokens"`
		OutputTokens int `json:"output_tokens"`
	} `json:"usage"`
}

func Chat(prompt, system string) (string, int, int, error) {
	apiKey := os.Getenv("ANTHROPIC_API_KEY")
	if apiKey == "" {
		return "", 0, 0, fmt.Errorf("ANTHROPIC_API_KEY not set")
	}

	body, _ := json.Marshal(Request{
		Model:     "claude-haiku-4-5-20251001",
		MaxTokens: 1024,
		System:    system,
		Messages:  []Message{{Role: "user", Content: prompt}},
	})

	req, _ := http.NewRequest("POST", anthropicURL, bytes.NewReader(body))
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")
	req.Header.Set("content-type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", 0, 0, err
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	var result Response
	if err := json.Unmarshal(raw, &result); err != nil {
		return "", 0, 0, err
	}
	if len(result.Content) == 0 {
		return "", 0, 0, fmt.Errorf("empty response: %s", string(raw))
	}

	return result.Content[0].Text,
		result.Usage.InputTokens,
		result.Usage.OutputTokens,
		nil
}

func main() {
	prompt := "Explain what makes Go suitable for building AI microservices in 3 bullet points."
	if len(os.Args) > 1 {
		prompt = os.Args[1]
	}

	fmt.Printf("prompt: %s\n---\n", prompt)
	start := time.Now()

	text, inTok, outTok, err := Chat(prompt, "You are a helpful assistant.")
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(text)
	fmt.Printf("\n[tokens: in=%d out=%d | latency: %dms]\n",
		inTok, outTok, time.Since(start).Milliseconds())
}
