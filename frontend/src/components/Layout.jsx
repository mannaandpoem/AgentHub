import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import {
  Bars3Icon,
  XMarkIcon,
  HomeIcon,
  BeakerIcon,
  CpuChipIcon,
  CodeBracketIcon
} from '@heroicons/react/24/outline';

function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
    { name: 'Create Agent', href: '/agents/create', icon: BeakerIcon },
  ];

  const isCurrent = (path) => {
    return location.pathname === path;
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile sidebar */}
      <div className="md:hidden">
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 flex">
            <div
              className="fixed inset-0 bg-gray-600 bg-opacity-75 transition-opacity"
              onClick={() => setSidebarOpen(false)}
            />
            <div className="relative flex w-full max-w-xs flex-1 flex-col bg-slate-900 pb-4">
              <div className="absolute top-0 right-0 -mr-12 pt-2">
                <button
                  type="button"
                  className="ml-1 flex h-10 w-10 items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
                  onClick={() => setSidebarOpen(false)}
                >
                  <span className="sr-only">Close sidebar</span>
                  <XMarkIcon className="h-6 w-6 text-white" aria-hidden="true" />
                </button>
              </div>
              {/* Mobile sidebar content */}
              <div className="flex flex-shrink-0 items-center px-4 h-16 bg-slate-800">
                <CpuChipIcon className="h-8 w-8 text-blue-500 mr-2" />
                <span className="text-xl font-bold text-white">AgentHub</span>
              </div>
              <div className="mt-5 flex flex-grow flex-col">
                <nav className="flex-1 space-y-1 px-2" aria-label="Sidebar">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`${
                        isCurrent(item.href)
                          ? 'bg-slate-800 text-white'
                          : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                      } group flex items-center rounded-md px-2 py-2 text-base font-medium`}
                      onClick={() => setSidebarOpen(false)}
                    >
                      <item.icon
                        className={`mr-4 h-6 w-6 flex-shrink-0 ${
                          isCurrent(item.href) ? 'text-blue-500' : 'text-gray-400'
                        }`}
                        aria-hidden="true"
                      />
                      {item.name}
                    </Link>
                  ))}
                </nav>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Desktop sidebar */}
      <div className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0">
        <div className="flex min-h-0 flex-1 flex-col bg-slate-900">
          <div className="flex h-16 flex-shrink-0 items-center bg-slate-800 px-4">
            <CpuChipIcon className="h-8 w-8 text-blue-500 mr-2" />
            <span className="text-xl font-bold text-white">AgentHub</span>
          </div>
          <div className="flex flex-grow flex-col overflow-y-auto">
            <nav className="flex-1 space-y-1 px-2 py-4">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`${
                    isCurrent(item.href)
                      ? 'bg-slate-800 text-white'
                      : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                  } group flex items-center rounded-md px-2 py-2 text-sm font-medium`}
                >
                  <item.icon
                    className={`mr-3 h-6 w-6 flex-shrink-0 ${
                      isCurrent(item.href) ? 'text-blue-500' : 'text-gray-400'
                    }`}
                    aria-hidden="true"
                  />
                  {item.name}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex flex-shrink-0 bg-slate-800 p-4">
            <div className="text-xs text-gray-400">
              <p>AgentHub v0.1.0</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 md:pl-64">
        <div className="sticky top-0 z-10 md:hidden pl-1 pt-1 sm:pl-3 sm:pt-3 bg-slate-900">
          <button
            type="button"
            className="-ml-0.5 -mt-0.5 h-12 w-12 inline-flex items-center justify-center rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
            onClick={() => setSidebarOpen(true)}
          >
            <span className="sr-only">Open sidebar</span>
            <Bars3Icon className="h-6 w-6" aria-hidden="true" />
          </button>
        </div>
        <main className="flex-1 overflow-y-auto bg-slate-900">
          <div className="py-6">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 md:px-8">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default Layout;