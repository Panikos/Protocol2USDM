# Google Cloud Setup Script for Prompt Optimization
# Run this script to set up Google Cloud for Vertex AI Prompt Optimization

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Google Cloud Setup for Prompt Optimization" -ForegroundColor Cyan
Write-Host "======================================================================`n" -ForegroundColor Cyan

# Refresh PATH to detect newly installed gcloud
Write-Host "[1/6] Checking for Google Cloud SDK..." -ForegroundColor Yellow
Write-Host "Refreshing environment..." -ForegroundColor Gray
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$gcloudInstalled = Get-Command gcloud -ErrorAction SilentlyContinue

if (-not $gcloudInstalled) {
    Write-Host "❌ Google Cloud SDK not found" -ForegroundColor Red
    Write-Host "`nPlease install it from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    Write-Host "`nAfter installation, run this script again.`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Google Cloud SDK found`n" -ForegroundColor Green

# Authenticate
Write-Host "[2/6] Authenticating with Google Cloud..." -ForegroundColor Yellow
Write-Host "Opening browser for authentication...`n" -ForegroundColor Gray

gcloud auth application-default login

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Authentication failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Authentication successful`n" -ForegroundColor Green

# Get or create project
Write-Host "[3/6] Setting up project..." -ForegroundColor Yellow
$projectId = Read-Host "Enter your Google Cloud Project ID (or press Enter to create new)"

if ([string]::IsNullOrWhiteSpace($projectId)) {
    $projectId = "prompt-optimization-$(Get-Date -Format 'yyyyMMdd')"
    Write-Host "Creating new project: $projectId" -ForegroundColor Gray
    
    gcloud projects create $projectId
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Project creation failed" -ForegroundColor Red
        exit 1
    }
}

# Set active project
gcloud config set project $projectId
Write-Host "✅ Project set to: $projectId`n" -ForegroundColor Green

# Enable required APIs
Write-Host "[4/6] Enabling required APIs (this may take a few minutes)..." -ForegroundColor Yellow

$apis = @(
    "aiplatform.googleapis.com",
    "compute.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "  Enabling $api..." -ForegroundColor Gray
    gcloud services enable $api --quiet
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ API enablement failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Required APIs enabled`n" -ForegroundColor Green

# Install Python packages
Write-Host "[5/6] Installing Python packages..." -ForegroundColor Yellow
pip install google-cloud-aiplatform vertexai --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Package installation failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Python packages installed`n" -ForegroundColor Green

# Update .env file
Write-Host "[6/6] Updating .env file..." -ForegroundColor Yellow

$envPath = ".env"
$envContent = ""

if (Test-Path $envPath) {
    $envContent = Get-Content $envPath -Raw
}

# Add Google Cloud project ID if not present
if ($envContent -notmatch "GOOGLE_CLOUD_PROJECT") {
    Add-Content $envPath "`n# Google Cloud for Prompt Optimization"
    Add-Content $envPath "GOOGLE_CLOUD_PROJECT=$projectId"
    Add-Content $envPath "GOOGLE_CLOUD_LOCATION=us-central1"
    Write-Host "✅ Added GOOGLE_CLOUD_PROJECT to .env`n" -ForegroundColor Green
} else {
    Write-Host "ℹ️  GOOGLE_CLOUD_PROJECT already in .env`n" -ForegroundColor Blue
}

# Test the setup
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Testing Setup" -ForegroundColor Cyan
Write-Host "======================================================================`n" -ForegroundColor Cyan

Write-Host "Running test optimization..." -ForegroundColor Yellow

$testPrompt = "Extract schedule of activities from clinical trial protocol"

python -c @"
import os
os.environ['GOOGLE_CLOUD_PROJECT'] = '$projectId'

try:
    from prompt_optimizer import PromptOptimizer
    optimizer = PromptOptimizer()
    print('[INFO] Optimizer initialized successfully')
    print('[INFO] Ready to optimize prompts!')
except Exception as e:
    print(f'[ERROR] Test failed: {e}')
    exit(1)
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Setup complete and tested successfully!`n" -ForegroundColor Green
    
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Next Steps" -ForegroundColor Cyan
    Write-Host "======================================================================`n" -ForegroundColor Cyan
    
    Write-Host "1. Test prompt optimization:" -ForegroundColor Yellow
    Write-Host "   python prompt_optimizer.py --method google-zeroshot`n" -ForegroundColor Gray
    
    Write-Host "2. Run benchmark with optimization:" -ForegroundColor Yellow
    Write-Host "   python benchmark_prompts.py --test-set test_data/ --auto-optimize`n" -ForegroundColor Gray
    
    Write-Host "3. Compare results:" -ForegroundColor Yellow
    Write-Host "   python compare_benchmark_results.py baseline.json optimized.json`n" -ForegroundColor Gray
    
    Write-Host "Your project ID: $projectId" -ForegroundColor Green
    Write-Host "Saved to: .env`n" -ForegroundColor Green
} else {
    Write-Host "`n❌ Setup test failed. Please check errors above.`n" -ForegroundColor Red
    exit 1
}

Write-Host "======================================================================`n" -ForegroundColor Cyan
