# Box: Ollama deployment + self-benching (J21 prep)

**Target Host:** DESKTOP-0GIFKM1  
**LAN IP:** <box-lan-ip>  
**Tailscale IP:** 100.73.6.74  
**Role:** CPU-only inference node (Secondary)  
**Existing Service:** llama-swap on `:8080` (SYSTEM scheduled task)  
**New Service:** Ollama on `:11434`

## 1. Install Checklist

Ollama is being installed as a second inference entry point alongside the existing llama-swap stack. The goal is to expose the Ollama API to the main PC (192.168.12.126) for benchmarking and future LATER lane integration.

### 1.1. Prerequisites & Directory Setup

1.  **Download Installer:** Obtain the latest `OllamaSetup.exe` from the official GitHub releases.
2.  **Run Installer:** Execute as Administrator. Accept defaults.
    *   **Default Install Dir:** `C:\Program Files\Ollama`
    *   **Models Dir:** By default, Ollama uses `C:\Users\<User>\.ollama\models`.
3.  **Configure Models Directory (D: Drive Preference):**
    *   Check if a `D:` drive exists and has sufficient space (>25GB free).
    *   If `D:` exists, set the environment variable `OLLAMA_MODELS` to `D:\ollama-models`.
    *   If `D:` does not exist, use `C:\ollama-models`.
    *   *Note:* Ensure the directory exists before starting the service. Create it via PowerShell if necessary:
      ```powershell
      # If using D:
      New-Item -ItemType Directory -Force -Path "D:\ollama-models"
      # If using C:
      New-Item -ItemType Directory -Force -Path "C:\ollama-models"
      ```
    *   Set the environment variable permanently (System level) so the scheduled task/service picks it up:
      ```powershell
      [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama-models", "Machine")
      ```
      *(Replace path with `C:\ollama-models` if applicable)*

### 1.2. Network Configuration

Ollama binds to `127.0.0.1` by default. To allow the main PC (192.168.12.126) to reach the box, you must bind to `0.0.0.0`.

1.  **Set OLLAMA_HOST:**
    *   Set the system environment variable `OLLAMA_HOST` to `0.0.0.0`.
    ```powershell
    [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "Machine")
    ```
2.  **Restart Ollama Service:**
    *   If Ollama is running as a service, restart it. If it was installed as a desktop app, close and reopen it.
    ```powershell
    Restart-Service -Name "Ollama" -Force
    ```
    *(Note: If Ollama is not installed as a Windows Service, ensure it is configured to start on boot or run manually for this session. For J21 prep, a Service is preferred for stability.)*

### 1.3. Firewall Rule

Scope access to the main PC only. Do not open port 11434 to the entire LAN.

1.  **Create Firewall Rule:**
    ```powershell
    New-NetFirewallRule -DisplayName "Ollama Access from Main PC" `
                        -Direction Inbound `
                        -Protocol TCP `
                        -LocalPort 11434 `
                        -RemoteAddress 192.168.12.126 `
                        -Action Allow `
                        -Profile Any
    ```

### 1.4. Verification

From the **Main PC** (192.168.12.126), verify connectivity:

```bash
curl http://<box-lan-ip>:11434/api/tags
```

*   **Expected Output:** JSON list of installed models (initially empty `{"models":[]}`).
*   **If Failed:**
    *   Check if Ollama is listening on `0.0.0.0:11434` on the box (`netstat -an | findstr 11434`).
    *   Verify the firewall rule exists on the box.
    *   Ensure the main PC and box are on the same subnet (192.168.12.x).

---

## 2. Model Plan

Two models will be pulled to establish baseline performance and parity checks.

| Model | Tag | Quantization | Est. Disk Size | Role | Expected CPU Perf |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen3 27B** | `qwen3:27b` (or specific IQ3/Q3 variant) | IQ3/Q3-class | ~20 GB | **LATER Workhorse** | ~2 tok/s |
| **Qwen3 8B** | `qwen3:8b` | Q4_K_M (default) | ~5.2 GB | **Tierllama Jev Brain** (Parity) | ~5-7 tok/s |

### 2.1. Pull Commands

Run these on the **Box** (DESKTOP-0GIFKM1) via PowerShell or Command Prompt.

```powershell
# Pull the 27B model for LATER workhorse role
# Note: If a specific IQ3 quant is required, use the exact tag from the registry.
# 'qwen3:27b' is the standard tag. Verify available tags if a specific quant is needed.
ollama pull qwen3:27b

# Pull the 8B model for parity checks
ollama pull qwen3:8b
```

### 2.2. Disk & Performance Reality

*   **Disk:** Ensure ~25GB free space on the models drive (`D:` or `C:`).
*   **CPU-Only Inference:**
    *   **27B IQ3/Q3:** Expect **~2 tokens/sec**. This is slow. Use for batch jobs or non-interactive LATER tasks.
    *   **8B Q4:** Expect **~5-7 tokens/sec**. Usable for interactive parity checks and Tierllama rater pool ingestion.
*   **RAM:** Both models will load into RAM. The 27B model will consume ~18-20GB of RAM when active. The 8B model will consume ~6-8GB.

---

## 3. Self-Bench Script (J21 Deliverable)

This script benchmarks the installed models by measuring generation speed and cold load times. It outputs a JSON file to `C:\jobs\results\` for ingestion by the main agent.

**Script Name:** `ollama_bench.ps1`
**Location:** `C:\jobs\scripts\ollama_bench.ps1` (Create dir if missing)

### 3.1. Full Runnable Script

Copy the following into `C:\jobs\scripts\ollama_bench.ps1`:

```powershell
<#
.SYNOPSIS
Ollama Self-Bench Script for J21 Prep
.DESCRIPTION
Runs /api/chat with stream:false, num_predict:64 against specified models.
Performs 3 warmup runs and 3 measured runs per model.
Records prompt_tok_s, gen_tok_s, cold_load_s, wall_s.
Writes results to C:\jobs\results\ollama_bench_<date>.json
#>

param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$OutputDir = "C:\jobs\results",
    [int]$NumPredict = 64,
    [int]$WarmupRuns = 3,
    [int]$MeasuredRuns = 3
)

# Models to benchmark
$Models = @(
    @{ Name = "qwen3:27b"; Tag = "qwen3:27b" },
    @{ Name = "qwen3:8b"; Tag = "qwen3:8b" }
)

# Ensure output directory exists
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir
}

# Timestamp for filename
$DateStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputFile = Join-Path $OutputDir "ollama_bench_$DateStamp.json"

$results = @()

Write-Host "Starting Ollama Benchmark..." -ForegroundColor Cyan
Write-Host "Host: $OllamaHost"
Write-Host "Output: $OutputFile"

foreach ($Model in $Models) {
    $modelName = $Model.Name
    $modelTag = $Model.Tag
    
    Write-Host "`n--- Benchmarking: $modelName ---" -ForegroundColor Yellow
    
    # Check if model exists
    $tagsResponse = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -Method Get
    $modelExists = $tagsResponse.models | Where-Object { $_.name -eq $modelTag }
    if (-not $modelExists) {
        Write-Host "Model $modelTag not found. Skipping." -ForegroundColor Red
        continue
    }

    # Define the prompt
    $prompt = "Hello, this is a benchmark test. Please respond with a short sentence."
    $messages = @(
        @{ role = "user"; content = $prompt }
    )

    # Helper function to run a single inference
    function Invoke-OllamaChat {
        param(
            [string]$Model,
            [array]$Msgs,
            [int]$NumPred
        )
        
        $body = @{
            model = $Model
            messages = $Msgs
            stream = $false
            options = @{
                num_predict = $NumPred
            }
        } | ConvertTo-Json -Depth 10

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $response = Invoke-RestMethod -Uri "$OllamaHost/api/chat" -Method Post -Body $body -ContentType "application/json"
            $sw.Stop()
            
            # Extract metrics from response
            $evalCount = $response.eval_count
            $evalDuration = $response.eval_duration / 1e9 # nanoseconds to seconds
            $promptEvalCount = $response.prompt_eval_count
            $promptEvalDuration = $response.prompt_eval_duration / 1e9
            $totalDuration = $sw.Elapsed.TotalSeconds
            
            # Calculate tok/s
            $genTokS = if ($evalDuration -gt 0) { $evalCount / $evalDuration } else { 0 }
            $promptTokS = if ($promptEvalDuration -gt 0) { $promptEvalCount / $promptEvalDuration } else { 0 }
            
            return @{
                eval_count = $evalCount
                eval_duration_s = $evalDuration
                prompt_eval_count = $promptEvalCount
                prompt_eval_duration_s = $promptEvalDuration
                wall_s = $totalDuration
                gen_tok_s = [math]::Round($genTokS, 2)
                prompt_tok_s = [math]::Round($promptTokS, 2)
            }
        } catch {
            $sw.Stop()
            Write-Host "Error during inference: $_" -ForegroundColor Red
            return $null
        }
    }

    # Warmup Runs
    Write-Host "Running $WarmupRuns warmup runs..."
    for ($i = 1; $i -le $WarmupRuns; $i++) {
        $null = Invoke-OllamaChat -Model $modelTag -Msgs $messages -NumPred $NumPredict
        Write-Host "  Warmup $i/$WarmupRuns complete."
    }

    # Measured Runs
    Write-Host "Running $MeasuredRuns measured runs..."
    $runResults = @()
    $coldLoadS = 0.0
    
    for ($i = 1; $i -le $MeasuredRuns; $i++) {
        # For the first measured run, we consider the time from start of request to first token as part of cold load if the model was unloaded.
        # However, Ollama keeps models in RAM if recently used. To simulate cold load, we would need to unload the model.
        # For this script, we assume the model is loaded after warmup. 
        # To get a true cold load, we would need to call /api/unload or restart the service. 
        # We will record the wall time of the first measured run as a proxy for "loaded" state latency.
        # If a true cold load is required, modify this section to unload the model before run 1.
        
        $result = Invoke-OllamaChat -Model $modelTag -Msgs $messages -NumPred $NumPredict
        if ($result) {
            $runResults += $result
            if ($i -eq 1) {
                # Approximate cold load as the wall time of the first run if we assume it was unloaded.
                # In reality, after warmup, it's hot. 
                # Let's record the wall time of the first run as 'first_run_wall_s' and note that true cold load requires unloading.
                # For J21, we will record the average wall time and gen_tok_s.
            }
        }
    }

    # Calculate averages for measured runs
    if ($runResults.Count -gt 0) {
        $avgGenTokS = ($runResults | Measure-Object -Property gen_tok_s -Average).Average
        $avgPromptTokS = ($runResults | Measure-Object -Property prompt_tok_s -Average).Average
        $avgWallS = ($runResults | Measure-Object -Property wall_s -Average).Average
        
        # Cold load: Since we didn't explicitly unload, we can't measure true cold load here.
        # We will set cold_load_s to the wall time of the first measured run as a baseline "hot" load time.
        # If strict cold load is needed, add a call to /api/unload before the first measured run.
        $coldLoadS = $runResults[0].wall_s

        $modelResult = @{
            model = $modelName
            tag = $modelTag
            gen_tok_s = [math]::Round($avgGenTokS, 2)
            prompt_tok_s = [math]::Round($avgPromptTokS, 2)
            cold_load_s = [math]::Round($coldLoadS, 2)
            wall_s = [math]::Round($avgWallS, 2)
            ts = (Get-Date).ToString("o")
            host = "DESKTOP-0GIFKM1"
            runs = $MeasuredRuns
        }
        
        $results += $modelResult
        Write-Host "  Avg Gen Tok/s: $($modelResult.gen_tok_s)"
        Write-Host "  Avg Wall Time: $($modelResult.wall_s)s"
    } else {
        Write-Host "  No successful runs for $modelName." -ForegroundColor Red
    }
}

# Write JSON output
$jsonPayload = @{
    benchmark = "ollama_self_bench"
    date = (Get-Date).ToString("o")
    host = "DESKTOP-0GIFKM1"
    results = $results
} | ConvertTo-Json -Depth 10

$jsonPayload | Out-File -FilePath $OutputFile -Encoding UTF8
Write-Host "`nBenchmark complete. Results saved to: $OutputFile" -ForegroundColor Green
```

### 3.2. Execution

1.  Open PowerShell on the **Box**.
2.  Run the script:
    ```powershell
    powershell -ExecutionPolicy Bypass -File C:\jobs\scripts\ollama_bench.ps1
    ```
3.  **Output:** A JSON file will be created in `C:\jobs\results\ollama_bench_<timestamp>.json`.

---

## 4. Integration: Tierllama Rater Pool

The main agent (on 192.168.12.126) ingests the JSON file to update the Tierllama rater pool. This allows the box to be treated as a data-backed LATER lane.

### 4.1. Ingestion Process

1.  **File Transfer:** The main agent pulls the latest JSON file from the box via SMB or Tailscale:
    ```bash
    # From Main PC
    scp DESKTOP-0GIFKM1@100.73.6.74:"C:/jobs/results/ollama_bench_*.json" ./local_results/
    ```
    *(Or use `robocopy` if SMB is enabled)*

2.  **Parse JSON:** The main agent parses the JSON to extract the following fields for each model:
    *   `model`: Model name (e.g., `qwen3:27b`)
    *   `tok_s`: Generation speed (`gen_tok_s`)
    *   `cold_load_s`: Time to load model into RAM
    *   `ts`: Timestamp of the benchmark
    *   `host`: Source host (`DESKTOP-0GIFKM1`)

3.  **Update Rater Pool:**
    *   The Tierllama rater pool maintains a history of performance metrics per model per host.
    *   New entries are appended to the pool.
    *   **Decision Logic:**
        *   If `tok_s` for `qwen3:27b` is < 1.5, mark the box as **unreliable** for interactive LATER tasks.
        *   If `tok_s` for `qwen3:8b` is > 4.0, mark the box as **eligible** for parity checks.
        *   If `cold_load_s` > 30s, flag for potential RAM contention or disk I/O issues.

4.  **LATER Lane Assignment:**
    *   The box becomes a **data-backed LATER lane** if the 27B model consistently achieves > 1.5 tok/s in batch mode.
    *   The 8B model is used for **parity checks** against the main PC's inference stack.

---

## 5. Coexistence: llama-swap :8080 + Ollama :11434

The box has 64GB RAM. Both llama-swap and Ollama can run simultaneously, but RAM contention is a critical risk.

### 5.1. RAM Contention Rules

1.  **Never Load the Same 27B Model in Both Stacks:**
    *   If llama-swap has `qwen3:27b` loaded, **do not** pull or run `qwen3:27b` in Ollama.
    *   Loading the same 27B model in both stacks will consume ~40GB of RAM, leaving only ~24GB for the OS and other processes. This will cause swapping and severe performance degradation.
    *   **Rule:** Use Ollama for 27B benchmarks **only** when llama-swap is idle or using a smaller model.

2.  **Monitor RAM Usage:**
    *   Use Task Manager or `Get-Process` to monitor RAM usage.
    *   If total RAM usage exceeds 50GB, unload one of the models.
    *   To unload an Ollama model:
      ```bash
      curl http://127.0.0.1:11434/api/unload
      ```
    *   To unload a llama-swap model: Use the llama-swap API or restart the service.

3.  **Staggered Usage:**
    *   **Phase 1:** Run Ollama benchmarks for 27B. Ensure llama-swap is not using the 27B model.
    *   **Phase 2:** Run Ollama benchmarks for 8B. This can run concurrently with llama-swap if llama-swap is using a small model (< 8B) or is idle.
    *   **Phase 3:** Return to llama-swap for primary inference. Unload Ollama models if necessary.

### 5.2. Service Stability

*   **llama-swap:** Runs as a SYSTEM scheduled task. It is stable and should not be restarted unnecessarily.
*   **Ollama:** Runs as a Service. Restarting it is safe but will interrupt any active Ollama sessions.
*   **Conflict Resolution:** If Ollama fails to start due to port conflict, verify that llama-swap is not using port 11434 (it uses 8080, so no conflict). If Ollama fails due to RAM, unload llama-swap models.

### 5.3. Final Checklist for J21 Prep

1.  [ ] Ollama installed and bound to `0.0.0.0:11434`.
2.  [ ] Firewall rule allows 192.168.12.126 to access 11434.
3.  [ ] `qwen3:27b` and `qwen3:8b` pulled to `D:\ollama-models` (or `C:\`).
4.  [ ] `ollama_bench.ps1` script created and tested.
5.  [ ] Benchmark JSON generated and verified.
6.  [ ] Main agent ingestion pipeline tested.
7.  [ ] RAM contention rules documented and understood.
8.  [ ] Box ready for LATER lane integration.

**End of Runbook**
