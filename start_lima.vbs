Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\GIT"
WshShell.Run "cmd /c set LIMA_API_KEY=xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw && set LIMA_CODE_SERVER_URL=https://chat.donglicao.com && set LIMA_CODE_API_KEY=xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw && cd /d D:\GIT && ""C:\Program Files\Git\usr\bin\winpty.exe"" node D:\GIT\deepcode-cli\node_modules\tsx\dist\cli.mjs D:\GIT\deepcode-cli\src\cli.tsx", 1, False
