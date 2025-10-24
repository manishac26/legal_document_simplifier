import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/Login";
import UploadPage from "./pages/UploadPage";
import { useEffect, useState } from "react";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // Check authentication status on app load
  useEffect(() => {
    const token = localStorage.getItem("authToken");
    setIsAuthenticated(!!token);
    setLoading(false);
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Routes>
      <Route 
        path="/" 
        element={isAuthenticated ? <Navigate to="/upload" replace /> : <LoginPage />} 
      />
      <Route 
        path="/upload" 
        element={isAuthenticated ? <UploadPage /> : <Navigate to="/" replace />} 
      />
    </Routes>
  );
}

export default App;