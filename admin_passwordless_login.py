"""
后端管理面板免密登录实现
使用 JWT Token 和 Session 管理
"""

import jwt
import time
import secrets
from datetime import datetime, timedelta
from functools import wraps

# 配置
JWT_SECRET_KEY = secrets.token_urlsafe(32)  # 生产环境应从环境变量读取
JWT_ALGORITHM = 'HS256'
TOKEN_EXPIRE_HOURS = 24

def generate_token(username='admin'):
    """生成 JWT Token"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token):
    """验证 JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token 过期
    except jwt.InvalidTokenError:
        return None  # Token 无效

def require_auth(f):
    """装饰器：要求认证"""
    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        # 从 Cookie 或 Header 获取 Token
        token = request.cookies.get('admin_token') or \
                request.headers.get('Authorization', '').replace('Bearer ', '')

        if not token:
            # 未登录，重定向到登录页
            from starlette.responses import RedirectResponse
            return RedirectResponse(url='/admin/login')

        # 验证 Token
        payload = verify_token(token)
        if not payload:
            # Token 无效，重定向到登录页
            from starlette.responses import RedirectResponse
            response = RedirectResponse(url='/admin/login')
            response.delete_cookie('admin_token')
            return response

        # Token 有效，继续处理
        request.state.user = payload
        return await f(request, *args, **kwargs)

    return decorated_function


# FastAPI 路由示例
"""
from fastapi import FastAPI, Request, Response
from starlette.responses import HTMLResponse, RedirectResponse

app = FastAPI()

@app.get("/admin/login")
async def admin_login_page():
    '''登录页面'''
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>LiMa Admin Login</title>
        <style>
            body {
                font-family: -apple-system, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                background: #f5f5f7;
            }
            .login-box {
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                width: 320px;
            }
            h2 { margin: 0 0 20px; text-align: center; }
            input {
                width: 100%;
                padding: 12px;
                margin: 8px 0;
                border: 1px solid #ddd;
                border-radius: 6px;
                box-sizing: border-box;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #0071e3;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover { background: #0077ed; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>LiMa Admin</h2>
            <form method="post" action="/admin/login">
                <input type="password" name="password" placeholder="Enter password" required>
                <button type="submit">Login</button>
            </form>
        </div>
    </body>
    </html>
    '''
    return HTMLResponse(content=html)

@app.post("/admin/login")
async def admin_login(password: str, response: Response):
    '''处理登录请求'''
    # 简单密码验证（生产环境应使用更安全的方式）
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

    if password == ADMIN_PASSWORD:
        # 生成 Token
        token = generate_token('admin')

        # 设置 Cookie
        response = RedirectResponse(url='/admin', status_code=303)
        response.set_cookie(
            key='admin_token',
            value=token,
            httponly=True,
            secure=True,  # 生产环境启用 HTTPS
            samesite='lax',
            max_age=TOKEN_EXPIRE_HOURS * 3600
        )
        return response
    else:
        # 密码错误
        return RedirectResponse(url='/admin/login?error=1', status_code=303)

@app.get("/admin")
@require_auth
async def admin_panel(request: Request):
    '''管理面板（需要认证）'''
    user = request.state.user
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>LiMa Admin Panel</title>
    </head>
    <body>
        <h1>Welcome, {user['username']}!</h1>
        <p>Token expires at: {datetime.fromtimestamp(user['exp'])}</p>
        <a href="/admin/logout">Logout</a>
    </body>
    </html>
    '''
    return HTMLResponse(content=html)

@app.get("/admin/logout")
async def admin_logout():
    '''退出登录'''
    response = RedirectResponse(url='/admin/login', status_code=303)
    response.delete_cookie('admin_token')
    return response
"""

# 部署说明
DEPLOYMENT_GUIDE = """
# 后端管理面板免密登录部署指南

## 1. 安装依赖
pip install pyjwt

## 2. 配置环境变量
export JWT_SECRET_KEY="your-secret-key-here"
export ADMIN_PASSWORD="your-admin-password"

## 3. 集成到 routes/admin_ui.py
- 添加登录路由
- 添加认证装饰器
- 更新管理面板路由

## 4. 测试
- 访问 /admin 应重定向到 /admin/login
- 输入密码后应设置 Cookie
- 再次访问 /admin 应直接进入

## 5. 安全建议
- 使用强密码
- 启用 HTTPS
- 定期更换 Secret Key
- 限制登录尝试次数
- 记录登录日志

## 6. Token 刷新（可选）
实现 Token 自动刷新，提升用户体验

## 7. 多用户支持（可选）
- 用户数据库
- 角色权限
- 审计日志
"""

if __name__ == '__main__':
    print('='*70)
    print('后端管理面板免密登录实现')
    print('='*70)

    # 生成示例 Token
    token = generate_token('admin')
    print(f'\n示例 Token: {token[:50]}...')

    # 验证 Token
    payload = verify_token(token)
    if payload:
        print(f'验证成功: {payload["username"]}')
        print(f'过期时间: {datetime.fromtimestamp(payload["exp"])}')

    print('\n' + DEPLOYMENT_GUIDE)
