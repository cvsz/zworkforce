# Cài đặt

Hướng dẫn cài đặt chi tiết cho zRouter với mẹo troubleshooting.

---

## Yêu cầu

### Yêu cầu hệ thống

- **Node.js**: Phiên bản 20.0.0 trở lên
- **npm**: Phiên bản 10.0.0 trở lên (đi kèm Node.js)
- **OS**: macOS, Linux, Windows (khuyên dùng WSL)
- **Dung lượng**: ~200MB để cài đặt

### Kiểm tra Phiên bản

```bash
node --version
# Should show v20.x.x or higher

npm --version
# Should show 10.x.x or higher
```

**Chưa có Node.js?** Cài đặt từ [nodejs.org](https://nodejs.org/)

---

## Phương thức Cài đặt

### Cách 1: Cài Global (Khuyên dùng)

Cài zRouter toàn cục để dùng ở bất kỳ đâu:

```bash
npm install -g zrouter
```

**Khởi động zRouter:**

```bash
zrouter
```

**Lợi ích:**
- ✅ Chạy từ mọi thư mục
- ✅ Lệnh đơn giản: `zrouter`
- ✅ Auto-update với `npm update -g zrouter`

### Cách 2: Cài Local

Cài trong project cụ thể:

```bash
mkdir my-zrouter
cd my-zrouter
npm install zrouter
```

**Khởi động zRouter:**

```bash
npx zrouter
```

**Lợi ích:**
- ✅ Cô lập mỗi project
- ✅ Version control mỗi project
- ✅ Không làm bẩn global namespace

### Cách 3: Từ Source (Development)

Clone và build từ GitHub:

```bash
git clone https://github.com/decolua/zrouter.git
cd zrouter/app
npm install
npm run build
npm start
```

**Lợi ích:**
- ✅ Tính năng phát triển mới nhất
- ✅ Đóng góp cho dự án
- ✅ Tùy chỉnh

---

## Lần chạy Đầu tiên

### Khởi động Server

```bash
zrouter
```

**Điều gì xảy ra:**
1. Server khởi động tại `http://localhost:20128`
2. Dashboard tự động mở trong browser
3. Data directory được tạo tại `~/.zrouter`
4. API key được tạo tự động

### Đăng nhập Dashboard

**Credentials mặc định:**
- Mật khẩu: `123456`

**⚠️ Đổi mật khẩu ngay:**
1. Đăng nhập dashboard
2. Settings → Change Password
3. Dùng mật khẩu mạnh

### Lấy API Key

```
Dashboard → Settings → API Keys
→ Copy your API key
→ Use in CLI tools
```

**Ví dụ format API key:**
```
9r_1234567890abcdef1234567890abcdef
```

---

## Xác minh Cài đặt

### Kiểm tra trạng thái Server

```bash
curl http://localhost:20128/health
```

**Phản hồi dự kiến:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Liệt kê Model khả dụng

```bash
curl http://localhost:20128/v1/models \
  -H "Authorization: Bearer your-api-key"
```

**Phản hồi dự kiến:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "cc/claude-opus-4-5-20251101",
      "object": "model",
      "created": 1234567890,
      "owned_by": "claude-code"
    }
  ]
}
```

### Test Chat Completion

```bash
curl http://localhost:20128/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cc/claude-opus-4-5-20251101",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

---

## Cấu hình

### Biến môi trường

Tạo file `.env` hoặc set biến môi trường:

```bash
# Security (REQUIRED in production)
export JWT_SECRET="your-secure-secret-change-this"
export INITIAL_PASSWORD="your-password"

# Storage
export DATA_DIR="~/.zrouter"

# Server
export PORT="20128"
export NODE_ENV="production"

# Logging
export ENABLE_REQUEST_LOGS="false"
```

### Data Directory

**Vị trí mặc định:** `~/.zrouter`

**Nội dung:**
```
~/.zrouter/
  ├── db.json           # Database (providers, combos, usage)
  ├── api-keys.json     # API keys
  └── logs/             # Request logs (if enabled)
```

**Đổi vị trí:**

```bash
export DATA_DIR="/custom/path"
zrouter
```

### Cấu hình Port

**Port mặc định:** `20128`

**Đổi port:**

```bash
export PORT="3000"
zrouter
```

**Hoặc dùng command line:**

```bash
zrouter --port 3000
```

---

## Troubleshooting

### Port đã được dùng

**Lỗi:**
```
Error: listen EADDRINUSE: address already in use :::20128
```

**Giải pháp 1: Kill process hiện có**

```bash
# Find process using port 20128
lsof -i :20128

# Kill process
kill -9 <PID>
```

**Giải pháp 2: Dùng port khác**

```bash
zrouter --port 3000
```

### Permission Denied

**Lỗi:**
```
Error: EACCES: permission denied, mkdir '/usr/local/lib/node_modules/zrouter'
```

**Giải pháp: Dùng sudo (không khuyến nghị) hoặc fix npm permissions**

```bash
# Fix npm permissions (recommended)
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Then install again
npm install -g zrouter
```

### Node.js Phiên bản quá cũ

**Lỗi:**
```
Error: The engine "node" is incompatible with this module
```

**Giải pháp: Cập nhật Node.js**

```bash
# Using nvm (recommended)
nvm install 20
nvm use 20

# Or download from nodejs.org
```

### Dashboard không mở

**Vấn đề:** Dashboard không tự mở

**Giải pháp 1: Mở thủ công**

```
http://localhost:20128
```

**Giải pháp 2: Kiểm tra firewall**

```bash
# macOS: Allow Node.js in System Preferences → Security
# Linux: Check iptables
# Windows: Check Windows Firewall
```

### Không kết nối được Provider

**Vấn đề:** OAuth login thất bại hoặc API key không hợp lệ

**Giải pháp 1: Kiểm tra kết nối internet**

```bash
ping google.com
```

**Giải pháp 2: Kiểm tra trạng thái provider**

- Claude Code: [status.anthropic.com](https://status.anthropic.com)
- OpenAI: [status.openai.com](https://status.openai.com)
- Gemini: [status.cloud.google.com](https://status.cloud.google.com)

**Giải pháp 3: Tạo lại API key**

```
Dashboard → Provider → Disconnect → Reconnect
```

### Sử dụng RAM cao

**Vấn đề:** zRouter dùng quá nhiều RAM

**Giải pháp: Khởi động lại server**

```bash
# Stop
pkill -f zrouter

# Start
zrouter
```

**Hoặc dùng PM2 để auto-restart:**

```bash
npm install -g pm2
pm2 start zrouter --name zrouter
pm2 save
```

---

## Tùy chọn Deployment

### Phát triển cục bộ

```bash
npm install -g zrouter
zrouter
```

**Use case:** Code cá nhân, testing

### VPS/Cloud Server

```bash
# Install
npm install -g zrouter

# Configure
export JWT_SECRET="your-secure-secret"
export INITIAL_PASSWORD="your-password"
export NODE_ENV="production"

# Start with PM2
npm install -g pm2
pm2 start zrouter --name zrouter
pm2 save
pm2 startup
```

**Use case:** Team access, remote coding

### Docker

```bash
docker pull zrouter/zrouter:latest

docker run -d \
  -p 20128:20128 \
  -e JWT_SECRET="your-secure-secret" \
  -e INITIAL_PASSWORD="your-password" \
  -v zrouter-data:/root/.zrouter \
  --name zrouter \
  zrouter/zrouter:latest
```

**Use case:** Containerized deployment, Kubernetes

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:20128;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        
        # SSE support for streaming
        proxy_buffering off;
        proxy_read_timeout 86400;
    }
}
```

**Use case:** HTTPS, custom domain, load balancing

---

## Gỡ cài đặt

### Gỡ Global Installation

```bash
npm uninstall -g zrouter
```

### Xóa Data Directory

```bash
rm -rf ~/.zrouter
```

### Xóa Cấu hình

```bash
# Remove environment variables from shell config
nano ~/.bashrc  # or ~/.zshrc
# Delete zrouter-related exports
```

---

## Bước tiếp theo

- [Hướng dẫn Bắt đầu](../getting-started.md) - Kết nối provider và bắt đầu code
- [Tính năng](../features/) - Khám phá quota tracking, combos, deployment
- [Troubleshooting](../troubleshooting.md) - Sửa các vấn đề thường gặp

---

## Cần trợ giúp?

- **Website**: [zrouter.com](https://zrouter.com)
- **GitHub**: [github.com/decolua/zrouter](https://github.com/decolua/zrouter)
- **Issues**: [github.com/decolua/zrouter/issues](https://github.com/decolua/zrouter/issues)
