import React from 'react';
import { Link } from 'react-router-dom';

const NotFound: React.FC = () => {
	return (
		<div className="flex items-center justify-center p-4 py-16">
			<div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
				<div className="mb-6">
					<svg
						className="w-24 h-24 mx-auto text-gray-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						xmlns="http://www.w3.org/2000/svg"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="1.5"
							d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</div>

				<h1 className="text-3xl font-bold text-gray-800 mb-2">Page Not Found</h1>
				<p className="text-gray-600 mb-6">
					Sorry, the page you're looking for doesn't exist or has been moved.
				</p>

				<div className="space-y-4">
					<Link
						to="/"
						replace
						className="inline-block w-full md:w-auto px-6 py-3 bg-gradient-to-r
						           from-blue-600 to-indigo-700 text-white font-medium rounded-lg
						           hover:from-blue-700 hover:to-indigo-800 transition-all
						           shadow-md hover:shadow-lg"
					>
						Go to Dashboard
					</Link>

					<div className="mt-6 pt-6 border-t border-gray-200">
						<p className="text-sm text-gray-500">Error Code: 404</p>
					</div>
				</div>
			</div>
		</div>
	);
};

export default NotFound;