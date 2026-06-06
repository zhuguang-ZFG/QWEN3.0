# =============================================================================
# LiMa Nginx Configuration Templates
# =============================================================================
#
# These files are the authoritative Nginx configuration for the LiMa VPS.
# Apply with: bash deploy_nginx.sh
#
# Files:
#   chat.donglicao.com.conf   - Main chat proxy (OpenAI/Anthropic API + web)
#   www.donglicao.com.conf    - Public website (static + demo API)
#   donglicao.conf            - api.donglicao.com (auxiliary API proxy)
#   lima.257339.xyz.conf      - Legacy domain redirect
#   http_limits.conf          - Rate limit zones (include in nginx.conf http{})
#
# VPS paths:
#   /etc/nginx/conf.d/        - Server block configs
#   /etc/nginx/nginx.conf     - Main config (http_limits go in http{} block)
#
# SSL certs: Let's Encrypt at /etc/letsencrypt/live/<domain>/
# =============================================================================
