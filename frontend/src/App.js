import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardLayout from "@/components/DashboardLayout";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Alerts from "@/pages/Alerts";
import Observations from "@/pages/Observations";
import DroneMissions from "@/pages/DroneMissions";
import Predictions from "@/pages/Predictions";
import GEEIndices from "@/pages/GEEIndices";
import AIAnalysis from "@/pages/AIAnalysis";
import Forests from "@/pages/Forests";
import Users from "@/pages/Users";

export default function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="observations" element={<Observations />} />
              <Route path="drones" element={<DroneMissions />} />
              <Route path="predictions" element={<Predictions />} />
              <Route path="gee" element={<GEEIndices />} />
              <Route path="ai" element={<AIAnalysis />} />
              <Route path="forests" element={<Forests />} />
              <Route
                path="users"
                element={
                  <ProtectedRoute roles={["admin"]}>
                    <Users />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}
