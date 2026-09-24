param(
    [string]$RepoUrl = "",
    [string]$MainBranch = "main",
    [string]$DevBranch = "develop",
    [string]$CommitMessage = "Initial commit"
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Roroboregos GitHub upload helper" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed or is not available in PATH. Install Git first and run this script again."
    exit 1
}

if (-not $RepoUrl) {
    $RepoUrl = Read-Host "Paste your GitHub repository URL (example: https://github.com/USERNAME/Roroboregos-code.git)"
}

if (-not $RepoUrl) {
    Write-Error "No repository URL was provided."
    exit 1
}

$repoFolder = (Get-Location).Path
Write-Host "Project folder: $repoFolder"
Write-Host "Repository URL: $RepoUrl"

# Initialize git if this folder is not already a repo.
if (-not (Test-Path ".git")) {
    Write-Host "Initializing Git repository..."
    git init
}

# Add all files to the repo.
Write-Host "Adding files to Git..."
git add .

# Make the first commit.
Write-Host "Creating commit..."
try {
    git commit -m $CommitMessage
}
catch {
    Write-Host "No changes to commit or Git user config missing. If needed, configure your name/email first:"
    Write-Host "git config --global user.name \"YOUR_NAME\""
    Write-Host "git config --global user.email \"YOUR_EMAIL@EXAMPLE.COM\""
    exit 1
}

# Make sure a branch exists.
try {
    git branch --show-current | Out-Null
    $currentBranch = git branch --show-current
}
catch {
    $currentBranch = ""
}

if (-not $currentBranch) {
    git branch -M $MainBranch
}
else {
    # If the repo already has a branch name, keep it unless it is empty.
    if ($currentBranch -ne $MainBranch) {
        git branch -M $MainBranch
    }
}

# Add remote repository.
$remoteExists = $false
try {
    git remote get-url origin | Out-Null
    $remoteExists = $true
}
catch {
    $remoteExists = $false
}

if ($remoteExists) {
    git remote set-url origin $RepoUrl
}
else {
    git remote add origin $RepoUrl
}

# Push main branch.
Write-Host "Pushing main branch to GitHub..."
git push -u origin $MainBranch

# Create and push develop branch if desired.
if ($DevBranch) {
    $branchExists = $false
    try {
        git show-ref --verify --quiet "refs/heads/$DevBranch"
        $branchExists = $true
    }
    catch {
        $branchExists = $false
    }

    if (-not $branchExists) {
        Write-Host "Creating development branch: $DevBranch"
        git checkout -b $DevBranch
        git push -u origin $DevBranch
    }
    else {
        Write-Host "Branch $DevBranch already exists locally."
    }
}

Write-Host "" 
Write-Host "Upload complete!" -ForegroundColor Green
Write-Host "Your repository is now on GitHub." -ForegroundColor Green
Write-Host "Open: $RepoUrl" -ForegroundColor Green
Write-Host "" 
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  git status"
Write-Host "  git checkout main"
Write-Host "  git checkout develop"
Write-Host "  git add ."
Write-Host "  git commit -m \"Update\""
Write-Host "  git push"
