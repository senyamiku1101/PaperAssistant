# Windows 定时任务配置

## 使用 PowerShell 创建

```powershell
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument "D:\Documents\AIProjects\PaperAssistant\scripts\monitor.py" `
  -WorkingDirectory "D:\Documents\AIProjects\PaperAssistant"

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am

Register-ScheduledTask `
  -TaskName "PaperAssistantMonitor" `
  -Action $action `
  -Trigger $trigger `
  -Description "每周文献监控 - 搜索 OpenAlex 新论文并生成报告"
```

## 手动运行

```powershell
Start-ScheduledTask -TaskName "PaperAssistantMonitor"
```

## 查看状态

```powershell
Get-ScheduledTask -TaskName "PaperAssistantMonitor"
```

## 删除

```powershell
Unregister-ScheduledTask -TaskName "PaperAssistantMonitor" -Confirm:$false
```

## 注意事项

1. 确保 Python 在系统 PATH 中可用，或用 Python 完整路径替换 `"python"`
2. 如果使用虚拟环境，将 `-Execute` 改为虚拟环境中的 Python 路径（如 `"D:\Documents\AIProjects\PaperAssistant\.venv\Scripts\python.exe"`）
3. 首次创建后可在"任务计划程序" (taskschd.msc) 中查看和调整
4. 建议将触发器时间设为周一上午 9:00，确保周末的新论文被覆盖
