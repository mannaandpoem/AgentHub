import React from 'react';
import { Link } from 'react-router-dom';
import { HomeIcon } from '@heroicons/react/24/outline';

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="bg-slate-800 rounded-lg p-8 shadow-lg text-center max-w-md">
        <h1 className="text-3xl font-bold text-white mb-4">404</h1>
        <h2 className="text-xl font-semibold text-gray-300 mb-6">Page Not Found</h2>
        <p className="text-gray-400 mb-8">
          The page you are looking for doesn't exist or has been moved.
        </p>
        <Link
          to="/dashboard"
          className="btn btn-primary inline-flex items-center"
        >
          <HomeIcon className="h-5 w-5 mr-2" />
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}

export default NotFound;