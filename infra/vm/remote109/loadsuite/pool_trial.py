"""앱 DB 풀만 조정하는 시험용 변환. 동작·도메인 코드는 유지한다."""


def patch_pool(source: str) -> str:
    """배포 원본의 기본값이 예상과 다르면 변경을 거부한다."""
    for token in ['"pool_size": 3,', '"max_overflow": 2,', '"pool_timeout": 3,']:
        if source.count(token) != 1:
            raise ValueError("unexpected_pool_source")
    return source.replace('"pool_size": 3,', '"pool_size": 5,').replace(
        '"max_overflow": 2,', '"max_overflow": 5,'
    )
