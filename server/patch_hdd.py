s = open('srvpage.py', encoding='utf-8').read()
i = s.index("               'hdd': ")
j = s.index('\n', i)
new = ("               'hdd': (_sh(['sh', '-c', \"df -h /mnt/hdd | awk 'NR==2{print $5\\\" used of \\\"$2}'\"])"
       " if subprocess.run(['findmnt', '/mnt/hdd'], capture_output=True).returncode == 0"
       " else 'NOT MOUNTED - Nextcloud/Jellyfin stopped'),")
s = s[:i] + new + s[j:]
open('srvpage.py', 'w', encoding='utf-8').write(s)
import ast; ast.parse(s); print('ok')
