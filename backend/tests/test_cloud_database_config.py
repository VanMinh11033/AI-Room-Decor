from app.core.database import build_connect_args


def test_build_connect_args_local_mariadb():
    url = "mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor?charset=utf8mb4"
    args = build_connect_args(url, ssl_verify=False)
    assert args == {}


def test_build_connect_args_sqlite():
    url = "sqlite:///./test.db"
    args = build_connect_args(url)
    assert args == {"check_same_thread": False}


def test_build_connect_args_tidb_cloud_auto_detect():
    url = "mysql+pymysql://user:pass@gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/ai_room_decor"
    args = build_connect_args(url, ssl_verify=False)
    assert args.get("ssl_verify_cert") is True
    assert args.get("ssl_verify_identity") is True


def test_build_connect_args_with_ssl_flag():
    url = "mysql+pymysql://user:pass@db.example.com:3306/ai_room_decor"
    args = build_connect_args(url, ssl_verify=True)
    assert args.get("ssl_verify_cert") is True
    assert args.get("ssl_verify_identity") is True


def test_build_connect_args_with_ssl_ca():
    url = "mysql+pymysql://user:pass@db.example.com:3306/ai_room_decor"
    args = build_connect_args(url, ssl_ca="/etc/ssl/certs/ca.pem")
    assert args.get("ssl_ca") == "/etc/ssl/certs/ca.pem"
    assert args.get("ssl_verify_cert") is True
