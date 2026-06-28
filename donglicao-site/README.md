# donglicao-site（官网 v1）

## 规范源定位

`donglicao-site/` 是 **LiMa 当前生产官网的静态 HTML 版本**，由 `scripts/deploy_unified.py` 的 `_DEPLOY_EXCLUDES` 显式排除，通常通过手动 `scp`/CI 增量同步到 VPS `/www/wwwroot/donglicao-site/`。

## 负责页面

- 首页：`index.html`
- 产品页：`product-draw.html`、`product-write.html`、`product-human.html`
- 定价页：`pricing.html`
- 法律页：`privacy.html`、`terms.html`
- 旧版 Chat 入口：`chat.html`（`routes/static_files.py` 根路径 `/` 的兜底候选）
- 共享资源：`styles.css`、`product.css`、`site.js`、`galaxy.js`、`solar-system.js`、`assets/`

## 与 donglicao-site-v2 的关系

- `donglicao-site-v2/` 是基于 Next.js 的新官网实验/迭代版本，通过 `.github/workflows/deploy-site-v2.yml` 部署到另一目录（`secrets.SITE_V2_DIR`）。
- 两者当前并非互斥替代关系：v1 承担产品详情页与已验证的 SEO 落地页；v2 承担博客、英文站、设计系统迭代。
- 若未来决定完全迁移到 v2，需先把 v1 中的产品页、定价页、法律页在 v2 中重建，并更新 `routes/static_files.py` 的 `/` 兜底逻辑，再归档 v1。

## 维护注意

- 修改后请同步到 VPS `/www/wwwroot/donglicao-site/`。
- 不要直接删除本目录，除非已完成向 `donglicao-site-v2` 的内容迁移并同步路由。
