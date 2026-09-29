import { useQuery } from '@tanstack/react-query';
import api from '../api/axiosInstance';

export const useIndustry = () =>
	useQuery({
		queryKey: ['industry'],
		queryFn: async () => {
			const res = await api.get('/MasterData/api/industry');
			return res.data.data;
		},
		staleTime: 1000 * 60 * 10,
		gcTime: 1000 * 60 * 15,
		refetchOnWindowFocus: false
	});