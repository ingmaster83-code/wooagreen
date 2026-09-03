require 'json'

module Jekyll
  class ParkPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      items = load_json(site, '_data_src/parks.json')

      Jekyll.logger.info "ParkGenerator:", "#{items.size}개 공원 페이지 생성 중..."
      items.each do |c|
        next if c['slug'].to_s.strip.empty?
        site.pages << ParkPage.new(site, c)
      end

      Jekyll.logger.info "ParkGenerator:", "완료 (#{items.size}개)"
    end

    private

    def load_json(site, path)
      file = File.join(site.source, path)
      return [] unless File.exist?(file)
      JSON.parse(File.read(file, encoding: 'utf-8'))
    rescue => e
      Jekyll.logger.warn "ParkGenerator:", "#{path} 로드 실패: #{e.message}"
      []
    end
  end

  class ParkPage < Page
    def initialize(site, c)
      @site = site
      @base = site.source
      @dir  = "park/#{c['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'park.html')
      self.data.merge!(c)
      self.data['layout']      = 'park'
      self.data['title']       = build_title(c)
      self.data['description'] = build_desc(c)
    end

    private

    def build_title(c)
      loc = [c['doShort'], c['sigungu']].compact.join(' ')
      "#{c['parkName']} #{loc} 위치 시설정보"
    end

    def build_desc(c)
      loc = [c['doShort'], c['sigungu']].compact.join(' ')
      "#{loc} #{c['parkName']}의 위치, 운동시설·놀이시설 정보를 확인하세요."[0, 155]
    end
  end
end
