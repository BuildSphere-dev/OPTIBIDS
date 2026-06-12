// auth.js — safe login/signup/logout helpers without infinite loop

// Only check /auth/me if token exists
async function safeGetUser() {
  const token = localStorage.getItem("token");
  if (!token) return null;     // <-- DO NOT call backend without token

  try {
    return await api.get("/auth/me");
  } catch {
    return null;
  }
}

const auth = {

  async signup() {
    const email = document.getElementById("su-email").value.trim();
    const password = document.getElementById("su-password").value;
    const confirm = document.getElementById("su-password-confirm").value;
    const role = document.getElementById("su-role").value;

    if (!email || !password) return alert("Email and password required");
    if (password !== confirm) return alert("Passwords do not match");

    try {
      await api.post("/auth/register", { email, password, role });
      alert("Account created — please login");
      window.location.href = "/login.html";
    } catch (e) {
      alert("Signup failed: " + e.message);
    }
  },

  async login() {
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    if (!email || !password) return alert("Email and password required");

    try {
      const data = await api.post("/auth/login", { email, password });

      if (!data.access_token) throw new Error("Login failed");

      localStorage.setItem("token", data.access_token);

      const user = await safeGetUser();
      if (!user) throw new Error("Invalid token");

      if (user.role === "admin") window.location.href = "/admin/admin_dashboard.html";
      else window.location.href = "/applicant/applicant_dashboard.html";

    } catch (e) {
      alert("Login failed: " + e.message);
      localStorage.removeItem("token");
    }
  },

  logout() {
    localStorage.removeItem("token");
    window.location.href = "/login.html";
  }
};


// -------------------------------------------------------------
// AUTO-REDIRECT LOGIC (SAFELY CHECK TOKEN FIRST)
// -------------------------------------------------------------
(async () => {

  const token = localStorage.getItem("token");

  // If not logged in → stay on login page
  if (!token) return;

  // Fetch user only if token exists
  const user = await safeGetUser();

  if (!user) {
    // token invalid → logout
    localStorage.removeItem("token");
    return;
  }

  // If already logged in → redirect from login page to dashboard
  if (window.location.pathname.includes("login")) {
    if (user.role === "admin") window.location.href = "/admin/admin_dashboard.html";
    else window.location.href = "/applicant/applicant_dashboard.html";
  }

})();
