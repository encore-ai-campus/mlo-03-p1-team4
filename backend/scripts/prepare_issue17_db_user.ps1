param([switch]$Apply)

$ErrorActionPreference = "Stop"

function ConvertFrom-SecureInput {
    param([Parameter(Mandatory = $true)][System.Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

$pythonPath = Join-Path $env:USERPROFILE "miniforge3\envs\pro_1\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "프로젝트 전용 Python 환경 pro_1을 찾지 못했습니다: $pythonPath"
}

$adminSecure = $null
$runnerSecure = $null
$adminPassword = $null
$runnerPassword = $null
$envNames = @("ISSUE17_DB_ADMIN_PASSWORD", "ISSUE17_RUNNER_PASSWORD")
$originalOutputEncoding = $OutputEncoding

$pythonCode = @'
import hashlib
import os
import sys

import pymysql

account = "issue17_runner"
host = "100.100.100.1"
schema = "spacecube_test"
connection = None
step = "MariaDB 관리자 연결"

try:
    connection = pymysql.connect(
        host="100.100.100.31",
        port=3306,
        user="root",
        password=os.environ["ISSUE17_DB_ADMIN_PASSWORD"],
        database="mysql",
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        autocommit=True,
    )
    with connection.cursor() as cursor:
        step = "서버 인증 설정 확인"
        cursor.execute("SELECT VERSION(), @@old_passwords")
        version, old_passwords = cursor.fetchone()
        if "MariaDB" not in version or old_passwords != 0:
            raise RuntimeError("unsupported MariaDB authentication setup")

        step = "시험 스키마 확인"
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
            (schema,),
        )
        if cursor.fetchone()[0] != 1:
            raise RuntimeError("test schema missing")

        step = "계정 존재 확인"
        cursor.execute(
            "SELECT COUNT(*) FROM mysql.user WHERE User=%s AND Host=%s",
            (account, host),
        )
        exists = cursor.fetchone()[0] == 1
        password = os.environ["ISSUE17_RUNNER_PASSWORD"]
        digest = hashlib.sha1(hashlib.sha1(password.encode("utf-8")).digest()).hexdigest().upper()
        password_hash = "*" + digest
        if not exists:
            step = "제한 계정 생성"
            cursor.execute(
                "CREATE USER 'issue17_runner'@'100.100.100.1' IDENTIFIED BY PASSWORD %s",
                (password_hash,),
            )
        else:
            step = "제한 계정 비밀번호 설정"
            cursor.execute(
                "ALTER USER 'issue17_runner'@'100.100.100.1' IDENTIFIED BY PASSWORD %s",
                (password_hash,),
            )

        step = "기존 권한 회수"
        cursor.execute(
            "REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'issue17_runner'@'100.100.100.1'"
        )
        step = "시험 스키마 권한 부여"
        cursor.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON `spacecube_test`.* "
            "TO 'issue17_runner'@'100.100.100.1'"
        )

        step = "권한 범위 검증"
        cursor.execute(
            "SELECT Select_priv, Insert_priv, Update_priv, Delete_priv, "
            "Create_priv, Drop_priv, Grant_priv FROM mysql.user "
            "WHERE User=%s AND Host=%s",
            (account, host),
        )
        global_privileges = cursor.fetchone()
        cursor.execute(
            "SELECT Select_priv, Insert_priv, Update_priv, Delete_priv, "
            "Create_priv, Drop_priv, Grant_priv FROM mysql.db "
            "WHERE User=%s AND Host=%s AND Db=%s",
            (account, host, schema),
        )
        schema_privileges = cursor.fetchone()

        if global_privileges != ("N",) * 7:
            raise RuntimeError("global privileges remain")
        if schema_privileges != ("Y", "Y", "Y", "Y", "N", "N", "N"):
            raise RuntimeError("schema privileges do not match")

    print("계정 확인 완료: issue17_runner@100.100.100.1")
    print("권한: spacecube_test의 SELECT, INSERT, UPDATE, DELETE만")
except Exception as error:
    code = error.args[0] if isinstance(error, pymysql.MySQLError) and error.args else "-"
    print(f"계정 설정 실패 단계: {step}; 오류 종류: {type(error).__name__}; DB 오류 코드: {code}")
    print("비밀번호나 전체 연결 문자열은 출력하지 않습니다.")
    sys.exit(1)
finally:
    if connection is not None:
        connection.close()
'@

try {
    $adminSecure = Read-Host ".31 MariaDB root 비밀번호 (화면에 표시되지 않음)" -AsSecureString
    $runnerSecure = Read-Host "새 issue17_runner 비밀번호 (화면에 표시되지 않음)" -AsSecureString
    $adminPassword = ConvertFrom-SecureInput -Value $adminSecure
    $runnerPassword = ConvertFrom-SecureInput -Value $runnerSecure
    if ([string]::IsNullOrWhiteSpace($adminPassword) -or [string]::IsNullOrWhiteSpace($runnerPassword)) {
        throw "비밀번호는 비워 둘 수 없습니다."
    }
    if ($runnerPassword.Length -lt 16) {
        throw "시험 계정 비밀번호는 16자 이상으로 설정해 주세요."
    }

    Write-Output "적용 대상: issue17_runner@100.100.100.1"
    Write-Output "권한 범위: spacecube_test의 SELECT, INSERT, UPDATE, DELETE만"
    if (-not $Apply) {
        $confirmation = Read-Host "이 계정 설정을 제출하려면 APPLY를 입력하세요"
        if ($confirmation -cne "APPLY") {
            throw "계정 설정을 취소했습니다."
        }
    }

    $env:ISSUE17_DB_ADMIN_PASSWORD = $adminPassword
    $env:ISSUE17_RUNNER_PASSWORD = $runnerPassword
    # Windows PowerShell 5.1의 -c 인자 전달은 Python 코드의 따옴표를 제거할 수 있다.
    # 표준 입력으로 UTF-8 소스를 전달해 계정/호스트 문자열을 그대로 유지한다.
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $pythonCode | & $pythonPath -
    if ($LASTEXITCODE -ne 0) {
        throw "시험 계정 설정이 완료되지 않았습니다."
    }
}
finally {
    $OutputEncoding = $originalOutputEncoding
    foreach ($name in $envNames) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
    if ($adminSecure) { $adminSecure.Dispose() }
    if ($runnerSecure) { $runnerSecure.Dispose() }
    $adminPassword = $null
    $runnerPassword = $null
}
