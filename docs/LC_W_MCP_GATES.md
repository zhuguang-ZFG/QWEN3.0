# LiMa MCP gates inventory (radar §七)

一键跑全部 MCP smoke（默认均为 skip，除非对应 `LIMA_*_MCP=1`）：

```powershell
python scripts/smoke_mcp_gates.py
python scripts/smoke_mcp_gates.py --live
```

包含：fetch、filesystem、github、postgres、brave、firecrawl、playwright。

安全扫描 bundle（Trivy + Grype + Syft，report-only；二进制缺失记为 skip）：

```powershell
python scripts/run_security_gates.py
python scripts/run_security_gates.py --strict
```
