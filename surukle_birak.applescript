on run
	display dialog "PDF banka ekstresini bu simgenin üzerine sürükleyip bırak." & return & return & "Excel dosyası PDF'in yanına kaydedilir ve açılır." buttons {"Tamam"} default button 1 with title "Ekstre Çevir" with icon note
end run

on open birakilanlar
	set klasor to do shell script "dirname " & quoted form of (POSIX path of (path to me))
	set betik to klasor & "/calistir.sh"
	if (do shell script "test -x " & quoted form of (klasor & "/.venv/bin/python") & " && echo var || echo yok") is "yok" then
		display notification "İlk açılış: gerekli bileşenler kuruluyor. Bu yalnız bir kez olur." with title "Ekstre Çevir"
	end if
	repeat with dosya in birakilanlar
		set yol to POSIX path of dosya
		if yol ends with ".pdf" or yol ends with ".PDF" then
			try
				set cikti to do shell script quoted form of betik & " " & quoted form of yol
				do shell script "open " & quoted form of (last paragraph of cikti)
			on error hata
				display dialog "Çevrilemedi:" & return & yol & return & return & hata buttons {"Tamam"} default button 1 with title "Ekstre Çevir" with icon caution
			end try
		else
			display dialog "Yalnız PDF dosyası bırakabilirsin:" & return & yol buttons {"Tamam"} default button 1 with title "Ekstre Çevir" with icon caution
		end if
	end repeat
end open
