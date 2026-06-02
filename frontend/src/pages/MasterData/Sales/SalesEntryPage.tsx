import React, { useEffect, useState } from "react";

interface Tab {
	key: number;
	label: string;
}

const SalesEntryPage: React.FC = () => {

	const [id, setId] = useState<"Add" | "Edit" | "View">("View");
	const [salesno, setSalesno] = useState("");
	const [salType, setSalType] = useState("");
	const [npwpType, setNpwpType] = useState("");
	const [menu, setMenu] = useState(1);
	const [baru, setBaru] = useState("");
	const [showNewDialog, setShowNewDialog] = useState(false);
	const [noreg, setNoreg] = useState("");
	const [tabs, setTabs] = useState<Tab[]>([]);

	useEffect(() => {
		const params = new URLSearchParams(window.location.search);

		const paramId = (params.get("id") || "View") as "Add" | "Edit" | "View";
		const paramSalesno = params.get("salesno") || "";
		const paramSalType = params.get("sal_type") || "";
		const paramBaru = params.get("new") || "";

		setId(paramId);
		setSalesno(paramSalesno);
		setSalType(paramSalType);
		setBaru(paramBaru);

		if (paramId === "Add" && paramBaru === "baru") {
			setShowNewDialog(true);
		}
	}, []);

	useEffect(() => {
		let currentBroker = salType;
		let currentNpwp = npwpType;

		if (id === "Add" && !salesno) {
			currentBroker = "";
			currentNpwp = "";
		}

		const newTabs: Tab[] = [];

		if (currentBroker === "PT" && currentNpwp === "PT") {
			newTabs.push({ key: 1, label: "Main" });
			newTabs.push({ key: 2, label: "PIC" });
			newTabs.push({ key: 3, label: "Bank Account" });
			newTabs.push({ key: 4, label: "Tax" });
			newTabs.push({ key: 5, label: "Document Broker" });
			newTabs.push({ key: 6, label: "Additional Notes" });
		}
		else if (currentBroker === "PT" && currentNpwp === "PR") {
			newTabs.push({ key: 1, label: "Main" });
			newTabs.push({ key: 3, label: "Bank Account" });
			newTabs.push({ key: 4, label: "Tax" });
			newTabs.push({ key: 5, label: "Document Broker" });
			newTabs.push({ key: 6, label: "Additional Notes" });
		}
		else if (currentBroker === "PR" && currentNpwp === "PR") {
			newTabs.push({ key: 1, label: "Main" });
			newTabs.push({ key: 3, label: "Bank Account" });
			newTabs.push({ key: 4, label: "Tax" });
			newTabs.push({ key: 5, label: "Document Sales" });
			newTabs.push({ key: 6, label: "Additional Notes" });
		}
		else {
			newTabs.push({ key: 1, label: "Main" });
			newTabs.push({ key: 3, label: "Bank Account" });
			newTabs.push({ key: 4, label: "Tax" });
			newTabs.push({ key: 5, label: "Document Sales" });
			newTabs.push({ key: 6, label: "Additional Notes" });
		}

		setTabs(newTabs);
	}, [salType, npwpType, id, salesno]);

	const handleTabClick = (tabKey: number) => {
		if (id === "Add" && !salesno) {
			alert("Please save the Main form first to generate Sales No.");
			return;
		}
		setMenu(tabKey);
	};

	const handleDialogOk = () => {
		if (!noreg.trim()) {
			alert("Please fill the Request Number");
			return;
		}
		alert(`✅ Request submitted: ${noreg}\n\nSales number will be generated after saving Main form.`);

		setShowNewDialog(false);
	};

	const handleBackToList = () => {
		window.location.href = "/sales";
	};

	const modeColor = {
		Add: "emerald",
		Edit: "amber",
		View: "blue",
	}[id];

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg overflow-hidden">
					{/* Header */}
					<div className="px-6 py-5 border-b flex items-center justify-between bg-gray-50">
						<div className="flex items-center gap-4">
							<h1 className="text-2xl font-bold text-gray-800">Sales Entry</h1>
							<span className={`px-4 py-1 rounded-full text-sm font-semibold bg-${modeColor}-100 text-${modeColor}-700`}>
								{id === "Add" ? "NEW" : id.toUpperCase()}
							</span>
							{salesno && (
								<span className="text-sm font-medium text-gray-500">
									Sales No: <span className="font-semibold text-gray-900">{salesno}</span>
								</span>
							)}
						</div>

						<button
							onClick={handleBackToList}
							className="flex items-center gap-2 px-5 py-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-all"
						>
							← Back to Sales List
						</button>
					</div>

					{/* Tabs - exactly like PHP cssmenu */}
					<div className="border-b bg-white">
						<div className="flex overflow-x-auto hide-scrollbar">
							{tabs.map((tab) => (
								<button
									key={tab.key}
									onClick={() => handleTabClick(tab.key)}
									className={`px-8 py-4 text-sm font-medium whitespace-nowrap border-b-2 transition-all ${menu === tab.key
											? "border-blue-600 text-blue-600"
											: "border-transparent text-gray-600 hover:text-gray-900"
										}`}
								>
									{tab.label}
								</button>
							))}
						</div>
					</div>

					{/* Content Area (replaces iframe) */}
					<div className="p-8 min-h-[600px]">
						{menu === 1 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">Main Form</p>
								<p className="text-sm mt-2">sales_main.php content goes here</p>
								<p className="text-xs text-gray-400 mt-8">Implement your form fields (Name, Address, ID Card, etc.)</p>
							</div>
						)}
						{menu === 2 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">PIC</p>
								<p className="text-sm mt-2">sales_pic.php content goes here</p>
							</div>
						)}
						{menu === 3 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">Bank Account</p>
								<p className="text-sm mt-2">sales_bank_account.php content goes here</p>
							</div>
						)}
						{menu === 4 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">Tax</p>
								<p className="text-sm mt-2">sales_tax.php content goes here</p>
							</div>
						)}
						{menu === 5 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">
									{tabs.find(t => t.key === 5)?.label || "Document"}
								</p>
								<p className="text-sm mt-2">sales_file.php content goes here</p>
							</div>
						)}
						{menu === 6 && (
							<div className="text-center py-12 text-gray-500">
								<p className="text-lg font-medium">Additional Notes</p>
								<p className="text-sm mt-2">sales_notes.php content goes here</p>
							</div>
						)}
					</div>

					{/* Footer actions */}
					<div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
						{id !== "View" && (
							<button
								onClick={() => alert("✅ Save logic will be implemented in the Main tab")}
								className="px-8 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-xl hover:shadow-lg transition-all"
							>
								Save
							</button>
						)}
						<button
							onClick={handleBackToList}
							className="px-8 py-3 bg-white border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-100"
						>
							Cancel
						</button>
					</div>
				</div>
			</div>

			{/* New Sales Dialog (exactly like PHP dialogi) */}
			{showNewDialog && (
				<div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
						<div className="px-6 pt-6 pb-4">
							<h3 className="text-lg font-semibold text-gray-900">New Sales Entry</h3>
							<p className="text-sm text-gray-500 mt-1">Please enter Request Number</p>
						</div>

						<div className="px-6">
							<input
								type="text"
								placeholder="Request / No. Reg"
								value={noreg}
								onChange={(e) => setNoreg(e.target.value)}
								className="w-full border border-gray-300 focus:border-blue-500 focus:ring-blue-500 rounded-xl px-4 py-3 text-sm"
							/>
						</div>

						<div className="p-6 flex gap-3">
							<button
								onClick={() => {
									setShowNewDialog(false);
									handleBackToList();
								}}
								className="flex-1 py-3 text-gray-700 font-medium border border-gray-300 rounded-xl hover:bg-gray-100"
							>
								Cancel
							</button>
							<button
								onClick={handleDialogOk}
								className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl"
							>
								OK
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default SalesEntryPage;