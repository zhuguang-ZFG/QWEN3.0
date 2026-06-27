Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
report = "D:\QWEN3.0\tmp\grbl_fix_report.txt"
cmd = "cmd /c python D:\QWEN3.0\apply_grbl_fixes.py > D:\QWEN3.0\tmp\grbl_fix_console.txt 2>&1"
WshShell.Run cmd, 0, True
If FSO.FileExists(report) Then
    Set tf = FSO.OpenTextFile(report, 1)
    body = tf.ReadAll
    tf.Close
    If Len(body) > 1200 Then body = Right(body, 1200)
    MsgBox body, 64, "Grbl_Esp32 修复结果"
Else
    If FSO.FileExists("D:\QWEN3.0\tmp\grbl_fix_console.txt") Then
        Set tf = FSO.OpenTextFile("D:\QWEN3.0\tmp\grbl_fix_console.txt", 1)
        body = tf.ReadAll
        tf.Close
        MsgBox body, 48, "Grbl_Esp32 修复（无 report）"
    Else
        MsgBox "脚本未产生输出，请检查 Python / 路径权限。", 16, "Grbl_Esp32 修复失败"
    End If
End If
