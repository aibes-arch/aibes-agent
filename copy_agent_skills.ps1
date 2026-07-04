# 将当前根目录外的 aibes-skills 目录内容
# 完整镜像覆盖到当前项目 aibes_agent\skills 目录
# 注意：此操作会删除目标目录中源目录没有的文件

$SourceDir      = "E:\aibes-skills"
$DestinationDir = "E:\aibes-agent\aibes_agent\skills"

# 检查源目录是否存在
if (-not (Test-Path -Path $SourceDir -PathType Container)) {
    Write-Error "源目录不存在: $SourceDir"
    exit 1
}

# 确保目标目录存在
if (-not (Test-Path -Path $DestinationDir -PathType Container)) {
    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
}

# 使用 robocopy 镜像模式同步，但保留 aibes_agent.skills 包本身的 Python 文件
& robocopy $SourceDir $DestinationDir /MIR /R:3 /W:5 /XD ".git" /XF "__init__.py" "skill.py" "loader.py" "builder.py" /NJH /NJS

Write-Host "镜像同步完成: $SourceDir -> $DestinationDir"
