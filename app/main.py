import os, csv, io
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from jose import jwt, JWTError
from passlib.context import CryptContext
from .database import Base, engine, get_db, SessionLocal
from .models import User, Course, ExamPacket, Question, ExamSession, StudentAnswer, ProctoringLog, ViolationRule
from .algorithms import fisher_yates, essay_score, penalty_for

SECRET = os.getenv('JWT_SECRET', 'dev-only-change-this-secret-before-deploying')
ALGORITHM = 'HS256'
TOKEN_MINUTES = int(os.getenv('TOKEN_EXPIRE_MINUTES', '480'))
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
app = FastAPI(title='Sistem CBT D3 TI PNM', version='1.0.0', description='REST API untuk CBT, penilaian esai dan pengawasan ujian')
app.mount('/static', StaticFiles(directory='app/static'), name='static')

class LoginIn(BaseModel): nomor_induk: str; password: str
class CourseIn(BaseModel): kode: str; nama: str; semester: int = 1; sks: int = 2
class PacketIn(BaseModel): course_id: int; title: str; room_token: str; duration_minutes: int = 60; penalty_threshold: int = 100
class QuestionIn(BaseModel): kind: str; prompt: str; options: Optional[dict] = None; correct_option: Optional[str] = None; reference_answer: Optional[str] = None; keywords: list[str] = []; max_score: float = 1
class StartIn(BaseModel): room_token: str
class AutosaveIn(BaseModel): answers: dict[str, str]
class ViolationIn(BaseModel): session_id: int; code: str; detail: str = ''
class OverrideIn(BaseModel): score: float = Field(ge=0); note: str = ''

def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool:
    try: return pwd_context.verify(password, hashed)
    except Exception: return False

def create_token(user: User) -> str:
    now = datetime.utcnow()
    return jwt.encode({'sub': str(user.id), 'role': user.role, 'iat': now, 'exp': now + timedelta(minutes=TOKEN_MINUTES)}, SECRET, algorithm=ALGORITHM)

def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401, 'Token Bearer diperlukan')
    try: payload = jwt.decode(authorization.split(' ', 1)[1], SECRET, algorithms=[ALGORITHM]); uid = int(payload['sub'])
    except (JWTError, ValueError, KeyError): raise HTTPException(401, 'Token tidak valid atau kedaluwarsa')
    user = db.get(User, uid)
    if not user or not user.aktif: raise HTTPException(401, 'Pengguna tidak aktif')
    return user

def allow(*roles):
    def checker(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403, 'Peran pengguna tidak memiliki akses')
        return user
    return checker

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.nomor_induk == 'admin')):
            db.add_all([
                User(nomor_induk='admin', nama_lengkap='Administrator CBT', email='admin@cbt.local', password_hash=hash_password('Admin123!'), role='admin'),
                User(nomor_induk='dosen', nama_lengkap='Dosen Demo', email='dosen@cbt.local', password_hash=hash_password('Dosen123!'), role='dosen'),
                User(nomor_induk='pengawas', nama_lengkap='Pengawas Demo', email='pengawas@cbt.local', password_hash=hash_password('Awasi123!'), role='pengawas'),
                User(nomor_induk='223307105', nama_lengkap='Mahasiswa Demo', email='mahasiswa@cbt.local', password_hash=hash_password('Mhs12345!'), role='mahasiswa', kelas='TI-3D'),
            ])
        if not db.scalar(select(Course).where(Course.kode == 'TI101')):
            db.add(Course(kode='TI101', nama='Pengantar Teknologi Informasi', semester=1, sks=2))
        if not db.scalar(select(ViolationRule).where(ViolationRule.code == 'VIOL-01')):
            for code, label, points in [('VIOL-01','Pindah tab / halaman tersembunyi',25),('VIOL-02','Kehilangan fokus jendela',20),('VIOL-03','Keluar mode layar penuh',15),('VIOL-04','Klik kanan',10),('VIOL-05','Salin atau tempel teks',20)]: db.add(ViolationRule(code=code,label=label,points=points))
        db.commit()
    finally: db.close()

@app.on_event('startup')
def startup(): seed()

@app.get('/', response_class=HTMLResponse)
def home():
    with open('app/static/index.html', encoding='utf-8') as f: return f.read()

@app.get('/health')
def health(): return {'status':'ok','service':'Sistem CBT D3 TI PNM','time':datetime.utcnow().isoformat()}

@app.post('/api/v1/auth/login')
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.nomor_induk == data.nomor_induk))
    if not user or not user.aktif or not verify_password(data.password, user.password_hash): raise HTTPException(401, 'Nomor induk atau kata sandi salah')
    return {'access_token':create_token(user),'token_type':'bearer','profile':profile_data(user)}

def profile_data(u): return {'id':u.id,'nomor_induk':u.nomor_induk,'nama_lengkap':u.nama_lengkap,'role':u.role,'kelas':u.kelas}

@app.get('/api/v1/auth/profile')
def profile(user: User = Depends(current_user)): return profile_data(user)

@app.get('/api/v1/courses')
def courses(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{'id':c.id,'kode':c.kode,'nama':c.nama,'semester':c.semester,'sks':c.sks} for c in db.scalars(select(Course).order_by(Course.kode)).all()]

@app.post('/api/v1/courses')
def create_course(data: CourseIn, db: Session = Depends(get_db), user: User = Depends(allow('admin'))):
    if db.scalar(select(Course).where(Course.kode == data.kode)): raise HTTPException(409,'Kode mata kuliah sudah digunakan')
    obj=Course(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return {'id':obj.id,'kode':obj.kode,'nama':obj.nama}

@app.get('/api/v1/packets')
def packets(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows=db.scalars(select(ExamPacket).order_by(ExamPacket.id.desc())).all()
    return [{'id':p.id,'title':p.title,'course_id':p.course_id,'course':db.get(Course,p.course_id).nama,'room_token':p.room_token,'duration_minutes':p.duration_minutes,'penalty_threshold':p.penalty_threshold} for p in rows]

@app.post('/api/v1/packets')
def create_packet(data: PacketIn, db: Session = Depends(get_db), user: User = Depends(allow('admin','dosen'))):
    if not db.get(Course,data.course_id): raise HTTPException(404,'Mata kuliah tidak ditemukan')
    if data.duration_minutes < 1: raise HTTPException(422,'Durasi harus lebih dari 0')
    obj=ExamPacket(**data.model_dump(),created_by=user.id); db.add(obj); db.commit(); db.refresh(obj); return {'id':obj.id,'title':obj.title,'room_token':obj.room_token}

@app.get('/api/v1/packets/{packet_id}/questions')
def get_questions(packet_id: int, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen','pengawas'))):
    if not db.get(ExamPacket,packet_id): raise HTTPException(404,'Paket ujian tidak ditemukan')
    return [{'id':q.id,'kind':q.kind,'prompt':q.prompt,'options':q.options,'max_score':q.max_score,'keywords':q.keywords} for q in db.scalars(select(Question).where(Question.packet_id==packet_id)).all()]

@app.post('/api/v1/packets/{packet_id}/questions')
def add_question(packet_id: int, data: QuestionIn, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen'))):
    if not db.get(ExamPacket,packet_id): raise HTTPException(404,'Paket ujian tidak ditemukan')
    if data.kind not in ('mcq','essay'): raise HTTPException(422,'kind harus mcq atau essay')
    if data.kind=='mcq':
        if not data.options or set(data.options.keys()) != set('ABCDE'): raise HTTPException(422,'Soal pilihan ganda harus memiliki opsi A sampai E')
        if data.correct_option not in data.options: raise HTTPException(422,'Kunci jawaban harus salah satu opsi')
    elif not data.reference_answer: raise HTTPException(422,'Kunci referensi esai wajib diisi')
    obj=Question(packet_id=packet_id,**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return {'id':obj.id,'message':'Soal berhasil ditambahkan'}

@app.post('/api/v1/sessions/start')
def start_session(data: StartIn, db: Session=Depends(get_db), user: User=Depends(allow('mahasiswa'))):
    packet=db.scalar(select(ExamPacket).where(ExamPacket.room_token==data.room_token))
    if not packet: raise HTTPException(404,'Token ruang ujian tidak dikenal')
    if packet.starts_at and datetime.utcnow()<packet.starts_at: raise HTTPException(403,'Ujian belum dimulai')
    if packet.ends_at and datetime.utcnow()>packet.ends_at: raise HTTPException(403,'Jadwal ujian telah berakhir')
    existing=db.scalar(select(ExamSession).where(ExamSession.packet_id==packet.id,ExamSession.student_id==user.id,ExamSession.status=='active'))
    if existing: return {'session_id':existing.id,'status':existing.status,'message':'Melanjutkan sesi aktif'}
    questions=db.scalars(select(Question).where(Question.packet_id==packet.id)).all()
    if not questions: raise HTTPException(400,'Paket ujian belum memiliki soal')
    shuffled=fisher_yates(questions); orders={}
    for q in shuffled:
        if q.kind=='mcq': orders[str(q.id)]=fisher_yates(list(q.options.keys()))
    session=ExamSession(packet_id=packet.id,student_id=user.id,question_order=[q.id for q in shuffled],option_orders=orders)
    db.add(session); db.commit(); db.refresh(session)
    return {'session_id':session.id,'status':session.status,'question_count':len(shuffled),'message':'Sesi dimulai; urutan soal dan opsi diacak.'}

def get_owned_session(session_id, user, db):
    s=db.get(ExamSession,session_id)
    if not s: raise HTTPException(404,'Sesi tidak ditemukan')
    if user.role=='mahasiswa' and s.student_id!=user.id: raise HTTPException(403,'Sesi ini bukan milik Anda')
    return s

@app.get('/api/v1/sessions/{session_id}/paper')
def paper(session_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    s=get_owned_session(session_id,user,db)
    if s.status!='active': raise HTTPException(409,'Sesi ujian sudah tidak aktif')
    packet=db.get(ExamPacket,s.packet_id); elapsed=(datetime.utcnow()-s.started_at).total_seconds(); remaining=max(0,int(packet.duration_minutes*60-elapsed))
    if remaining==0: s.status='expired'; db.commit(); raise HTTPException(410,'Waktu ujian habis')
    answers={a.question_id:a.answer_text for a in db.scalars(select(StudentAnswer).where(StudentAnswer.session_id==s.id)).all()}
    out=[]
    for qid in s.question_order:
        q=db.get(Question,qid); options=None
        if q.kind=='mcq': options=[{'key':k,'text':q.options[k]} for k in s.option_orders.get(str(q.id),list(q.options.keys()))]
        out.append({'id':q.id,'kind':q.kind,'prompt':q.prompt,'options':options,'answer':answers.get(q.id,'')})
    return {'session_id':s.id,'packet_title':packet.title,'remaining_seconds':remaining,'questions':out}

@app.put('/api/v1/sessions/{session_id}/autosave')
def autosave(session_id: int, data: AutosaveIn, db: Session=Depends(get_db), user: User=Depends(allow('mahasiswa'))):
    s=get_owned_session(session_id,user,db)
    if s.status!='active': raise HTTPException(409,'Sesi tidak aktif')
    allowed=set(s.question_order)
    for raw_id, value in data.answers.items():
        try: qid=int(raw_id)
        except ValueError: continue
        if qid not in allowed: continue
        q=db.get(Question,qid); ans=db.scalar(select(StudentAnswer).where(StudentAnswer.session_id==s.id,StudentAnswer.question_id==qid))
        if not ans: ans=StudentAnswer(session_id=s.id,question_id=qid); db.add(ans)
        if q.kind=='mcq' and value not in (q.options or {}): raise HTTPException(422,f'Opsi tidak valid untuk soal {qid}')
        ans.answer_text=value[:20000]
    db.commit(); return {'status':'saved','saved_at':datetime.utcnow().isoformat()}

@app.post('/api/v1/sessions/{session_id}/submit')
def submit(session_id: int, db: Session=Depends(get_db), user: User=Depends(allow('mahasiswa'))):
    s=get_owned_session(session_id,user,db)
    if s.status=='submitted': return {'status':'submitted','total_score':s.total_score}
    if s.status!='active': raise HTTPException(409,'Sesi tidak aktif')
    packet=db.get(ExamPacket,s.packet_id); answers=db.scalars(select(StudentAnswer).where(StudentAnswer.session_id==s.id)).all(); byq={a.question_id:a for a in answers}
    total=0.0
    for qid in s.question_order:
        q=db.get(Question,qid); a=byq.get(qid)
        if not a:
            a=StudentAnswer(session_id=s.id,question_id=qid,answer_text=''); db.add(a)
        text=a.answer_text or ''
        if q.kind=='mcq':
            a.score=float(q.max_score if text==q.correct_option else 0); a.score_detail={'type':'mcq','correct':text==q.correct_option,'max_score':q.max_score}
        else:
            detail=essay_score(text,q.reference_answer or '',q.keywords or [],q.max_score)
            a.score=detail['score']; a.score_detail=detail
        total += float(a.score or 0)
    max_total=sum(float(db.get(Question,qid).max_score) for qid in s.question_order)
    s.total_score=round((total/max_total*100) if max_total else 0,2); s.status='submitted'; s.submitted_at=datetime.utcnow(); db.commit()
    return {'status':s.status,'total_score':s.total_score,'penalty_points':s.penalty_points,'integrity_index':s.integrity_index,'message':'Jawaban dinilai otomatis; hasil esai perlu verifikasi dosen.'}

@app.post('/api/v1/proctoring/event')
def proctor_event(data: ViolationIn, db: Session=Depends(get_db), user: User=Depends(allow('mahasiswa'))):
    s=get_owned_session(data.session_id,user,db)
    if s.status!='active': raise HTTPException(409,'Sesi tidak aktif')
    points=penalty_for(data.code); log=ProctoringLog(session_id=s.id,code=data.code,points=points,detail=data.detail[:500]); db.add(log)
    s.penalty_points += points; s.integrity_index=max(0,100-s.penalty_points)
    packet=db.get(ExamPacket,s.packet_id)
    if s.penalty_points>=packet.penalty_threshold: s.status='locked'
    db.commit()
    return {'logged':True,'code':data.code,'added_points':points,'penalty_points':s.penalty_points,'integrity_index':s.integrity_index,'status':s.status,'threshold':packet.penalty_threshold}

@app.get('/api/v1/proctoring/live/{packet_id}')
def live_proctoring(packet_id: int, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen','pengawas'))):
    packet=db.get(ExamPacket,packet_id)
    if not packet: raise HTTPException(404,'Paket tidak ditemukan')
    sessions=db.scalars(select(ExamSession).where(ExamSession.packet_id==packet_id).order_by(ExamSession.id.desc())).all()
    return [{'session_id':s.id,'student':db.get(User,s.student_id).nama_lengkap,'status':s.status,'penalty_points':s.penalty_points,'integrity_index':s.integrity_index,'score':s.total_score,'violations':db.query(ProctoringLog).filter_by(session_id=s.id).count()} for s in sessions]

@app.post('/api/v1/proctoring/unlock/{session_id}')
def unlock(session_id: int, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen','pengawas'))):
    s=db.get(ExamSession,session_id)
    if not s: raise HTTPException(404,'Sesi tidak ditemukan')
    if s.status!='locked': raise HTTPException(409,'Sesi tidak dalam status terkunci')
    s.status='active'; db.add(ProctoringLog(session_id=s.id,code='ADMIN-UNLOCK',points=0,detail=f'Dibuka kembali oleh {user.nama_lengkap}')); db.commit()
    return {'session_id':s.id,'status':s.status,'message':'Sesi dibuka kembali; poin penalti tetap tersimpan.'}

@app.get('/api/v1/grading/essay-detail/{answer_id}')
def essay_detail(answer_id: int, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen'))):
    a=db.get(StudentAnswer,answer_id)
    if not a: raise HTTPException(404,'Jawaban tidak ditemukan')
    q=db.get(Question,a.question_id)
    if q.kind!='essay': raise HTTPException(400,'Jawaban bukan esai')
    return {'answer_id':a.id,'question_id':q.id,'prompt':q.prompt,'student_answer':a.answer_text,'reference_answer':q.reference_answer,'keywords':q.keywords,'score':a.score,'detail':a.score_detail}

@app.put('/api/v1/grading/manual-override/{answer_id}')
def manual_override(answer_id: int, data: OverrideIn, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen'))):
    a=db.get(StudentAnswer,answer_id)
    if not a: raise HTTPException(404,'Jawaban tidak ditemukan')
    q=db.get(Question,a.question_id)
    if q.kind!='essay': raise HTTPException(400,'Hanya jawaban esai dapat ditinjau')
    if data.score>q.max_score: raise HTTPException(422,'Nilai melebihi skor maksimal')
    a.score=data.score; a.score_detail={**(a.score_detail or {}),'manual_override':True,'reviewer':user.nama_lengkap,'note':data.note,'reviewed_at':datetime.utcnow().isoformat()}
    s=db.get(ExamSession,a.session_id); db.commit()
    # hitung ulang total nilai setelah override
    answers=db.scalars(select(StudentAnswer).where(StudentAnswer.session_id==s.id)).all(); max_total=sum(float(db.get(Question,x).max_score) for x in s.question_order); raw=sum(float(x.score or 0) for x in answers); s.total_score=round(raw/max_total*100,2) if max_total else 0; db.commit()
    return {'answer_id':a.id,'score':a.score,'session_total_score':s.total_score,'reviewer':user.nama_lengkap}

@app.get('/api/v1/reports/packet/{packet_id}/export')
def export_report(packet_id: int, db: Session=Depends(get_db), user: User=Depends(allow('admin','dosen'))):
    packet=db.get(ExamPacket,packet_id)
    if not packet: raise HTTPException(404,'Paket tidak ditemukan')
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(['session_id','nomor_induk','nama','status','nilai_akhir','poin_penalti','indeks_integritas'])
    for s in db.scalars(select(ExamSession).where(ExamSession.packet_id==packet_id).order_by(ExamSession.id)).all():
        u=db.get(User,s.student_id); writer.writerow([s.id,u.nomor_induk,u.nama_lengkap,s.status,s.total_score,s.penalty_points,s.integrity_index])
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="hasil-ujian-{packet_id}.csv"'})
