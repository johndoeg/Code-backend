export interface CamContextProps {
	finType: string;
	indCor: '1' | '2';
	repeat: string;
	guarantor: '1' | '2';
	newCar: '1' | '2';
	status: string;
	purpoffinc: string;
	c2c: string;
	contType: string;
	public: string;
	boa: '1' | '2';
	bot: '1' | '2';
	apless: string;
	applno: string;
	insLoan: string;
	empId: string;
	aksesKhusus: boolean;
}

export interface MenuItem {
	id: number;
	label: string;
	path: string;
	component: React.ComponentType<any>;
}