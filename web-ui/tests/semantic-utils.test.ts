import { humanizePath } from '../lib/semantic/humanizePath';
import { evsUrl } from '../components/semantic/CodeLink';

describe('semantic utility helpers', () => {
  test('humanizePath renders nested semantic paths readably', () => {
    const path = '/study/versions/0/studyDesigns/0/activities/2/name';
    const label = humanizePath(path);

    expect(label).toBe('Study > Versions > #1 > Study Designs > #1 > Activities > #3 > Name');
  });

  test('humanizePath handles unknown keys with title casing', () => {
    const path = '/customSection/some_value';
    const label = humanizePath(path);

    expect(label).toBe('Custom Section > Some Value');
  });

  test('evsUrl points to NCIt browser for code', () => {
    const url = evsUrl('c98781');
    expect(url).toContain('ConceptReport.jsp');
    expect(url).toContain('code=C98781');
  });
});
