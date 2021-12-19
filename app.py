import hashlib

import jwt
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for

app = Flask(__name__)

client = MongoClient('localhost', 27017)
db = client.crud


SECRET_KEY = 'SPARTA'
@app.route('/')
def home():

    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        member = db.user.find_one({"id": payload['id']})['id']
        schd_data = list(db.schedule.find({'id': member}))  #회원정보(member) db와 스케줄정보(schedule) db를 id 값으로 연동
        area = ["60", "126"]

        # 토큰정보(유저의 ID)를 통해 현재 접속자의 스케줄 데이터를 조회
        schd_data = list(db.schedule.find({'id': member}))

        for item in schd_data:
            # 시간 정보 AM/PM 포맷팅 (hh:mm -> ex) AM 10:30)
            item['time'] = datetime.strftime(datetime.strptime(item['time'], '%H:%M'), '%p %I:%M')

        return render_template('list.html', schd_data=schd_data, area=area, userId=member)
    except jwt.ExpiredSignatureError:
        return redirect(url_for("login", msg="로그인 시간이 만료되었습니다."))
    except jwt.exceptions.DecodeError:
        return redirect(url_for("login"))

# 로그인 화면
@app.route('/login')
def login():
    return render_template('login.html')

# 회원가입 경로
@app.route('/register')
def register():
    return render_template("register.html")

# 리스트 경로
@app.route('/list')
def listregister():
    return render_template("list.html")

# 로그인 창에서 로그인 버튼 누르면 값 받아오기
@app.route('/api/login', methods=['POST'])
def api_login():
    id_receive = request.form['id_give']
    pw_receive = request.form['pw_give']
    pw_hash = hashlib.sha256(pw_receive.encode('utf-8')).hexdigest()
    result = db.user.find_one({'id': id_receive, 'pwd': pw_hash})

    if result is not None:
        payload = {
            'id': id_receive,
            'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지 => hour 또는 day
        }

        # .decode('utf-8')붙이면 서버에서 작동가능, 떼면 로컬에서 작동
        # jwt 이용 사용자 정보 암호화(단방향 암호화로 개발자가 사용자의 암호를 볼 수 없게함)
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')

        return jsonify({'result': 'success', 'token': token})

        # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


# 회원가입창에서 회원가입 버튼 누르면 값 받아오기
@app.route('/register/move', methods=['POST'])
def moverlogin():
    id = request.form["id"]
    pwd = request.form["pwdtxt"]
    pw_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

    doc = {"id":id, "pwd":pw_hash}
    db.user.insert_one(doc)
    return render_template('login.html')


#[아이디 중복확인 API]
# 이메일을 db에서 찾아서 클라이언트로 전달
@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup():
    id_receive = request.form['id_give']
    exists = bool(db.user.find_one({"id": id_receive}))
    return jsonify({'result': 'success', 'exists': exists})

'''
# API 역할을 하는 부분
@app.route('/api/list', methods=['GET'])
def show_stars():
    movie_stars = list(db.mystar.find({},{"_id":False}).sort('like', -1))
    return jsonify({'movie_stars': movie_stars})


@app.route('/api/like', methods=['POST'])
def like_star():
    name_receive = request.form['name_give']
    target_star = db.mystar.find_one({"name":name_receive})
    current_like = target_star["like"]

    new_like = current_like + 1
    db.mystar.update_one({"name":name_receive}, {"$set": {"like":new_like}})
    return jsonify({'msg': '좋아요 완료'})


@app.route('/api/delete', methods=['POST'])
def delete_star():
    name_receive = request.form['name_give']
    db.mystar.delete_one({"name": name_receive})
    return jsonify({'msg': '삭제 완료!'})
'''

if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)