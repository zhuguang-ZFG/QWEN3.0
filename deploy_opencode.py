#!/usr/bin/env python3
"""Deploy OpenCode optimization files to VPS."""

import paramiko
import os
import time

SERVER = '47.112.162.80'
REMOTE = '/opt/lima-router'
KEY = os.path.expanduser('~/.ssh/id_ed25519')

# Files to deploy
FILES = [
    # Existing OpenCode Phase 1
    'opencode_config.py',
    'context_compressor.py',
    'skills_injector.py',
    'model_resolver.py',
    'routing_selector.py',
    'speculative.py',
    'backends_constants.py',
    'http_response.py',
    'http_stream.py',
    'streaming_events.py',
    'routing_engine.py',
    'routing_executor.py',
    'routes/chat_stream.py',
    'routes/chat_endpoints.py',
    'routes/chat_handler_dispatch.py',
    'routes/system_endpoints.py',
    # Round 2 deep adaptation
    'opencode_error_adapter.py',       # NEW: overflow detection + error response
    'opencode_message_normalizer.py',   # NEW: message normalization pipeline
    'http_errors.py',                   # MODIFIED: BackendError.is_overflow
    'http_sync.py',                     # MODIFIED: overflow detection + usage thread safety
    'http_async.py',                    # MODIFIED: reasoning_effort passthrough
    'http_request_builder.py',          # MODIFIED: normalize_messages + reasoning_effort
    'response_builder.py',              # MODIFIED: usage parameter
    'chat_models.py',                   # MODIFIED: reasoning_effort field
    'routes/chat_handler.py',           # MODIFIED: 413 overflow response
    'routes/v3_adapters.py',            # MODIFIED: headers/reasoning_effort/usage
    'router_http_body.py',              # MODIFIED: normalize_messages integration
    'http_caller.py',                   # MODIFIED: facade re-exports (_get_client etc.)
]

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username='root', key_filename=KEY)
    
    sftp = ssh.open_sftp()
    for f in FILES:
        local = f'd:/QWEN3.0/{f}'
        remote = f'{REMOTE}/{f}'
        if os.path.exists(local):
            sftp.put(local, remote)
            print(f'uploaded {f}')
    
    sftp.close()
    
    # Restart server
    stdin, stdout, stderr = ssh.exec_command('pkill -9 -f "python3.10 server.py" || true')
    stdout.read()
    time.sleep(2)
    
    stdin, stdout, stderr = ssh.exec_command(
        f'cd {REMOTE} && nohup /usr/local/bin/python3.10 server.py '
        '> /var/log/lima-server.log 2>&1 &'
    )
    stdout.read()
    time.sleep(5)
    
    # Check if server is running
    stdin, stdout, stderr = ssh.exec_command('ss -tlnp | grep 8080')
    result = stdout.read().decode()
    if '8080' in result:
        print('Server UP on 8080')
    else:
        print('Server may not be running, checking logs...')
        stdin, stdout, stderr = ssh.exec_command('tail -20 /var/log/lima-server.log')
        print(stdout.read().decode())
    
    ssh.close()

if __name__ == '__main__':
    main()