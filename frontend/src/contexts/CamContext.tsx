import { useState, createContext, useContext, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { CamContextProps } from '../pages/types/cam';

const CamContext = createContext<CamContextProps | null>(null);

export function CamProvider({ children }: { children: React.ReactNode }) {
	const navigate = useNavigate();
	const location = useLocation();
	const [context, setContext] = useState<CamContextProps>({
		finType: '',
		indCor: '1',
		repeat: '1',
		guarantor: '1',
		newCar: '1',
		status: '',
		purpoffinc: '',
		c2c: '',
		contType: '',
		public: '',
		boa: '1',
		bot: '1',
		apless: '',
		applno: '',
		insLoan: '',
		empId: '',
		aksesKhusus: false
	});

	useEffect(() => {
		const params = new URLSearchParams(location.search);

		const newContext: CamContextProps = {
			finType: params.get('id1') || '',
			indCor: (params.get('id2') as '1' | '2') || '1',
			repeat: params.get('id3') || '1',
			guarantor: (params.get('id4') as '1' | '2') || '1',
			newCar: (params.get('id5') as '1' | '2') || '1',
			status: params.get('id6') || '',
			purpoffinc: params.get('id7') || '',
			c2c: params.get('id8') || '',
			contType: params.get('id9') || '',
			public: params.get('id13') || '',
			boa: (params.get('id11') as '1' | '2') || '1',
			bot: (params.get('id12') as '1' | '2') || '1',
			apless: params.get('apless') || '',
			applno: params.get('applno') || '',
			insLoan: params.get('ins_loan') || '',
			empId: localStorage.getItem('empId') || '',
			aksesKhusus: false
		};

		setContext(newContext);
	}, [location.search]);

	return (
		<CamContext.Provider value={context}>
			{children}
		</CamContext.Provider>
	);
}

export const useCamContext = () => {
	const context = useContext(CamContext);
	if (!context) {
		throw new Error('useCamContext must be used within CamProvider');
	}
	return context;
};