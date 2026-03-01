import React from 'react';

interface SyllabusPreviewProps {
  data: any;
  format?: string;
}

const SyllabusPreview: React.FC<SyllabusPreviewProps> = ({ data, format = 'docx' }) => {
  const calculateDate = (weekNum: string | number) => {
    if (!data.startDate) return '';
    const num = typeof weekNum === 'number' ? weekNum : parseInt(weekNum);
    if (isNaN(num)) return '';

    const start = new Date(data.startDate);
    const date = new Date(start);
    date.setDate(start.getDate() + (num - 1) * 7);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  if (format === 'json') {
    return (
      <pre className="bg-white p-6 rounded-lg shadow-sm overflow-auto text-sm font-mono text-gray-800 h-full border border-gray-200">
        {JSON.stringify(data, null, 2)}
      </pre>
    );
  }

  if (format === 'md') {
      // Simple markdown representation
      const mdContent = `
# ${data.course_info.title || 'Course Title'}
**${data.course_info.code}** | ${data.course_info.semester}
*Instructor: ${data.course_info.instructor}*

## Learning Goals
${data.learning_goals.map((g: any) => `- ${g.text}`).join('\n')}

## Schedule
| Week | Date | Topic | Assignment |
|------|------|-------|------------|
${data.schedule.map((s: any) => {
    const date = s.date || calculateDate(s.week);
    return `| ${s.week} | ${date} | ${s.topic} | ${s.assignment} |`;
}).join('\n')}

## Policies
${Object.entries(data.policies).map(([k, v]) => v ? `### ${k.replace(/_/g, ' ')}\n${v}` : '').filter(Boolean).join('\n\n')}
      `.trim();
      
      return (
          <pre className="bg-white p-6 rounded-lg shadow-sm overflow-auto text-sm font-mono text-gray-800 h-full whitespace-pre-wrap border border-gray-200">
              {mdContent}
          </pre>
      );
  }

  // Calculate spans for Week and Date columns
  const weekSpans = new Array(data.schedule.length).fill(0);
  const dateSpans = new Array(data.schedule.length).fill(0);

  if (data.schedule.length > 0) {
      let currentWeekStart = 0;
      for (let i = 1; i <= data.schedule.length; i++) {
          const prevWeek = data.schedule[i - 1]?.week;
          const currWeek = data.schedule[i]?.week;

          if (i === data.schedule.length || currWeek !== prevWeek) {
              weekSpans[currentWeekStart] = i - currentWeekStart;
              currentWeekStart = i;
          }
      }

      let currentDateStart = 0;
      for (let i = 1; i <= data.schedule.length; i++) {
          const prevDate = data.schedule[i - 1]?.date || calculateDate(data.schedule[i - 1]?.week);
          const currDate = data.schedule[i]?.date || calculateDate(data.schedule[i]?.week);

          if (i === data.schedule.length || currDate !== prevDate) {
              dateSpans[currentDateStart] = i - currentDateStart;
              currentDateStart = i;
          }
      }
  }

  // Default (DOCX/PDF view)
  return (
      <div className="max-w-3xl mx-auto bg-white p-4 md:p-8 min-h-full shadow-sm">
          <div className="text-center mb-8 border-b pb-6">
              <h1 className="text-2xl md:text-3xl font-bold text-gray-900">{data.course_info.title || 'Course Title'}</h1>
              <div className="text-gray-600 mt-2 text-base md:text-lg">
                  <span className="font-medium">{data.course_info.code}</span>
                  {data.course_info.semester && <span className="mx-2">•</span>}
                  <span>{data.course_info.semester}</span>
              </div>
              <p className="text-gray-800 mt-2 font-medium">{data.course_info.instructor}</p>
          </div>

          <div className="mb-8">
              <h2 className="text-xl font-bold text-gray-800 border-b-2 border-gray-200 pb-2 mb-4">Learning Goals</h2>
              <ul className="list-disc pl-5 space-y-2">
                  {data.learning_goals.map((goal: any) => (
                      <li key={goal.id} className="text-gray-700 leading-relaxed">{goal.text}</li>
                  ))}
              </ul>
          </div>

          <div className="mb-8">
              <h2 className="text-xl font-bold text-gray-800 border-b-2 border-gray-200 pb-2 mb-4">Schedule</h2>
              <div className="overflow-x-auto border rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200 border-collapse">
                      <thead className="bg-gray-50">
                          <tr>
                              <th className="px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20 border-b border-r">Week</th>
                              <th className="px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32 border-b border-r">Date</th>
                              <th className="px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-r">Topic</th>
                              <th className="px-4 md:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b">Assignment</th>
                          </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                          {data.schedule.map((item: any, index: number) => {
                              const weekSpan = weekSpans[index];
                              const dateSpan = dateSpans[index];
                              const displayDate = item.date || calculateDate(item.week);

                              return (
                              <tr key={index}>
                                  {weekSpan > 0 && (
                                      <td rowSpan={weekSpan} className="px-4 md:px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 border-r border-b align-top bg-white">{item.week}</td>
                                  )}
                                  {dateSpan > 0 && (
                                      <td rowSpan={dateSpan} className="px-4 md:px-6 py-4 whitespace-nowrap text-sm text-gray-500 border-r border-b align-top bg-white">{displayDate}</td>
                                  )}
                                  <td className="px-4 md:px-6 py-4 text-sm text-gray-900 border-r border-b align-top">{item.topic}</td>
                                  <td className="px-4 md:px-6 py-4 text-sm text-gray-500 border-b align-top">{item.assignment}</td>
                              </tr>
                          )})}
                      </tbody>
                  </table>
              </div>
          </div>

          <div className="mb-8">
              <h2 className="text-xl font-bold text-gray-800 border-b-2 border-gray-200 pb-2 mb-4">University Policies</h2>
              <div className="space-y-6">
                  {Object.entries(data.policies).map(([key, value]) => (
                      value ? (
                          <div key={key}>
                              <h3 className="font-bold text-gray-700 capitalize mb-1">{key.replace(/_/g, ' ')}</h3>
                              <p className="text-gray-600 leading-relaxed whitespace-pre-wrap">{value as string}</p>
                          </div>
                      ) : null
                  ))}
              </div>
          </div>
      </div>
  );
};

export default SyllabusPreview;
