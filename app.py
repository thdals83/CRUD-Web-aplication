import hashlib

from bson.json_util import dumps
from operator import itemgetter

import jwt
from bson import ObjectId
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

        # 토큰정보(유저의 ID)를 통해 현재 접속자의 스케줄 데이터를 조회
        schd_data = list(db.schedule.find({'id': member}))

        for item in schd_data:
            # 시간 정보 AM/PM 포맷팅 (hh:mm -> ex) AM 10:30)
            item['time'] = datetime.strftime(datetime.strptime(item['time'], '%H:%M'), '%p %I:%M')

        return render_template('list.html', schd_data=schd_data, userId=member)
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


# 스케줄 작성 경로
@app.route('/write')
def write():
    token_receive = request.cookies.get('mytoken')
    u_id = request.args.get('u_id')

    if token_receive is not None:
        if u_id is not None:
            schedules = db.schedule.find_one({'_id': ObjectId(u_id)})
            return render_template('write.html', schedules=schedules)
        return render_template('write.html')
    else:
        return render_template('write.html', isLogin=False, msg='로그인 후 이용하세요.')


# 회원가입창에서 회원가입 버튼 누르면 값 받아오기
@app.route('/register/move', methods=['POST'])
def moverlogin():
    id = request.form["id"]
    pwd = request.form["pwdtxt"]
    pw_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

    doc = {"id": id, "pwd": pw_hash}
    db.user.insert_one(doc)
    return render_template('login.html')


# 회원가입 창에서이메일을 db에서 찾아서 클라이언트로 전달
@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup():
    id_receive = request.form['id_give']
    exists = bool(db.user.find_one({"id": id_receive}))
    return jsonify({'result': 'success', 'exists': exists})


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
            # 'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지 => hour 또는 day
            'exp': datetime.utcnow() + timedelta(seconds=60 * 60)  # 로그인 5분 유지 => hour 또는 day
        }

        # .decode('utf-8')붙이면 서버에서 작동가능, 떼면 로컬에서 작동
        # jwt 이용 사용자 정보 암호화(단방향 암호화로 개발자가 사용자의 암호를 볼 수 없게함)
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')

        return jsonify({'result': 'success', 'token': token})

        # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


# 리스트 작성 창에서 리스트 양식 값들 받아오기
@app.route('/api/write', methods=['POST', 'GET'])
def api_write():
    token_receive = request.cookies.get('mytoken')  # 토큰 받아서 디코드
    payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])

    # db schedule에 들어갈 정보들 dictionary 작성
    id_receive = payload['id']
    title_receive = request.form['title_give']
    content_receive = request.form['content_give']
    time1_receive = request.form['time1_give']  # time1 -> hour
    time2_receive = request.form['time2_give']  # time2 -> minute
    day_receive = request.form.getlist('day_give[]')

    doc = {
        "id": id_receive,
        "subject": title_receive,
        "time": time1_receive + ':' + time2_receive,  # 시간
        "day": day_receive,
        "content": content_receive
    }
    # db에 저장하기
    db.schedule.insert_one(doc)
    return jsonify({'result': 'success', 'msg': '작성되었습니다.'})


# [리스트 정렬 API]
@app.route('/api/sort', methods=['POST'])
def api_sort():
    # 2차 정렬 선택 값
    # 상세: 입력순 -> normal, 시간 빠른순 -> fast, 매주 우선순 -> week
    action_receive = request.form['action_give']
    # 해당 유저의 전체 스케줄 데이터를 조회하기 위해 유저 ID값을 저장
    id_receive = request.form['id_give']

    # 유저 ID로 스케줄 전체 데이터를 조회
    filter_data = list(db.schedule.find({'id': id_receive}))

    # 전체보기 && 입력순
    if action_receive == 'normal':
        return jsonify({'result': dumps(filter_data)})

    # 전체보기 && 시간빠른순
    elif action_receive == 'fast':
        arr = sorted(filter_data, key=itemgetter('time'))
        return jsonify({'result': dumps(arr)})

    # 전체보기 && 매주 우선순
    elif action_receive == 'week':

        sortedArr = []

        for i in range(len(filter_data), 0, -1):
            if (filter_data[i - 1]['day'][-1] == 'false'):
                sortedArr.append(filter_data[i - 1])
            else:
                sortedArr.insert(0, filter_data[i - 1])
        return jsonify({'result': dumps(sortedArr)})


# [리스트 삭제 API]
@app.route('/api/remove', methods=['POST'])
def api_remove():
    # 삭제 할 스케줄 리스트 저장
    # 타입: Array
    # 요소 값: 각 스케줄의 _id
    remove_list_receive = request.form.getlist('remove_list_give[]')

    # 삭제 할 스케줄 정보가 존재 할 경우
    if len(remove_list_receive):
        for item_id in remove_list_receive:
            # 리스트를 순회하며 스케줄 데이터를 삭제
            # [MEMO] MongoDB를 _id를 참조하여 다루게 될 경우 ObjectId 를 사용해야함
            db.schedule.delete_one({'_id': ObjectId(item_id)})
        return jsonify({'result': 'success'})
    # 삭제 할 스케줄 정보가 없을 경우
    else:
        return jsonify({'result': 'fail', 'msg': '선택된 스케줄이 없습니다.'})


# 수정페이지
@app.route('/api/edit', methods=['POST'])
def api_edit():
    token_receive = request.cookies.get('mytoken')  # 토큰 받아서 디코드
    payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])

    id_receive = payload['id']
    _id = request.form['_id']
    title_receive = request.form['title_give']
    content_receive = request.form['content_give']
    time1_receive = request.form['time1_give']  # time1 -> hour
    time2_receive = request.form['time2_give']  # time2 -> minute
    day_receive = request.form.getlist('day_give[]')
    doc = {
        "id": id_receive,
        "subject": title_receive,
        "time": time1_receive + ':' + time2_receive,  # 시간
        "day": day_receive,
        "content": content_receive
    }

    # 수정된 내용들을 db shedule에 업로드 해주기
    db.schedule.update_one({'_id': ObjectId(_id)}, {'$set': doc})

    return jsonify({'result': 'success', 'msg': '수정되었습니다.'})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)
